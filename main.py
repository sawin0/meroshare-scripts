import csv
import os
import argparse
import requests
import constants
from datetime import date
import calendar
import json
from functools import cache, cached_property
import urllib3
import re
import xml.etree.ElementTree as ET

# Suppress only the insecure request warning for verify=False calls
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _extract_server_message(text: str):
    """Try to extract a useful server message from an exception text.

    Handles XML bodies like <exceptionMessage>...<message>...</message>...</exceptionMessage>
    and falls back to simple regex matches.
    """
    if not text:
        return None

    # If the repr included the XML, find first '<' and parse from there
    idx = text.find('<')
    if idx != -1:
        xml = text[idx:]
        try:
            root = ET.fromstring(xml)
            msg = root.find('.//message')
            if msg is not None and msg.text:
                return msg.text.strip()
        except Exception:
            pass

    # Try a direct regex for <message>..</message>
    m = re.search(r'<message>(.*?)</message>', text, re.S)
    if m:
        return m.group(1).strip()

    # Fallback: common human-readable errors
    m2 = re.search(r'Invalid [^\.]+\.?', text)
    if m2:
        return m2.group(0).strip()

    return None


def find_accounts_from_csv(user=None):
    acs = []
    with open(constants.ACCOUNTS_CSV_PATH, newline='') as file:
        csv_reader = csv.DictReader(file)
        if user:
            row = next((item for item in csv_reader if item['user'] == user), None)
            if row:
                return [Account(row['user'], row['dp'], row['username'], row['password'], row['crn'], row['pin'])]

            raise argparse.ArgumentError(name_arg, f"'{user}' user not found in accounts.csv file")
        else:
            acs.extend([Account(row['user'], row['dp'], row['username'], row['password'], row['crn'], row['pin']) for row in csv_reader])

    return acs


class Account:
    def __init__(self, user, dp, username, password, crn, pin):
        self.user = user
        self.dp = dp
        self.client_id = self.get_client_id(dp)
        self.username = username
        self.password = password
        self.crn = crn
        self.pin = pin

    @staticmethod
    def get_client_id(dp):
        """
        :param dp: depository participant id
        :return: integer, client id in meroshare system
        """
        capital = next(item for item in constants.CAPITALS if item['code'] == str(dp))
        return capital['id']


class Issue:
    def __init__(self, json_data):
        self._json_data = json_data

    def __str__(self):
        return (
            "******   COMPANY SHARE ID: {company_share_id}    ******{sep}{share_type} ({share_group}) - {subgroup}"
            " ({symbol}) - {name}{sep}{open_date} - {close_date}{sep}{status}{sep}"
            .format(
                sep=os.linesep,
                company_share_id=self.company_share_id,
                name=self.company_name,
                subgroup=self.subgroup,
                symbol=self.scrip,
                open_date=self.issue_open_date,
                close_date=self.issue_close_date,
                share_type=self.share_type_name,
                share_group=self.share_group_name,
                status=self.status.capitalize())
        )

    @property
    def is_unapplied_ordinary_share(self):
        return self.is_ordinary_shares and not self.is_applied

    @property
    def is_ipo(self):
        return True if self.share_type_name == 'IPO' else False

    @property
    def is_fpo(self):
        return True if self.share_type_name == 'FPO' else False

    @property
    def is_ordinary_shares(self):
        return True if self.share_group_name == 'Ordinary Shares' else False

    @property
    def status(self):
        return "applied" if self.is_applied else "not applied"

    @property
    def is_applied(self):
        # Determine applied status solely from the `action` field per user request.
        act = (self._json_data.get('action') or '')
        act_l = str(act).strip().lower()

        # Common action values that indicate the issue is applied or in-application
        applied_actions = {'edit', 'apply', 'applied', 'updated', 'inprocess', 'in_process', 'in-process'}
        return act_l in applied_actions

    @cached_property
    def company_share_id(self):
        return self._json_data.get("companyShareId")

    @cached_property
    def subgroup(self):
        return self._json_data.get("subGroup")

    @cached_property
    def scrip(self):
        return self._json_data.get("scrip")

    @cached_property
    def company_name(self):
        return self._json_data.get("companyName")

    @cached_property
    def share_type_name(self):
        return self._json_data.get("shareTypeName")

    @cached_property
    def share_group_name(self):
        return self._json_data.get("shareGroupName")

    @cached_property
    def status_name(self):
        return self._json_data.get("statusName")

    @cached_property
    def action(self):
        return self._json_data.get("action")

    @cached_property
    def issue_open_date(self):
        return self._json_data.get("issueOpenDate")

    @cached_property
    def issue_close_date(self):
        return self._json_data.get("issueCloseDate")


class UserSession:
    def __init__(self, account):
        self.account = account
        self.authorization = None
        self.branch_info = None
        self.set_user_session_defaults()

    def set_user_session_defaults(self):
        self.create_session()
        self.set_branch_info()

    def create_session(self):
        r = requests.post(
            'https://webbackend.cdsc.com.np/api/meroShare/auth/',
            json={
                'clientId': self.account.client_id,
                'username': self.account.username,
                'password': self.account.password
            },
            verify=False
        )

        # Debug: print raw response when requested
        if globals().get('args') and getattr(args, 'debug', False):
            try:
                print('=== AUTH RESPONSE ===')
                print('Status:', r.status_code)
                print(r.text)
            except Exception:
                pass

        # Try to parse useful response content for better diagnostics
        try:
            resp_json = r.json()
        except Exception:
            resp_json = None

        if r.ok:
            # Prefer header, but also accept common token keys from body
            auth = None
            auth = r.headers.get('Authorization') or r.headers.get('authorization')

            if not auth and isinstance(resp_json, dict):
                # Common fallback keys
                for key in ('Authorization', 'authorization', 'token', 'access_token'):
                    if key in resp_json:
                        auth = resp_json.get(key)
                        break

            if auth:
                self.authorization = auth
            else:
                raise ValueError(
                    "Unable to find Authorization in response for %s. Status=%s Response=%r"
                    % (self.account.username, r.status_code, resp_json or r.text)
                )
        else:
            # Provide more informative error including body when available
            raise ValueError(
                "Unable to create session for %s (status=%s): %r"
                % (self.account.username, r.status_code, resp_json or r.text)
            )

    def set_branch_info(self):
        bank = self.bank_info()
        # [{"code":"123","id":123,"name":"Nepal Mega Bank Ltd."}]
        r = requests.get(f"https://webbackend.cdsc.com.np/api/meroShare/bank/{bank['id']}",
                         headers=self.authorization_headers, verify=False)
        if r.ok:
            # [
            #     {
            #         "accountBranchId": 1234,
            #         "accountNumber": "123412341234",
            #         "accountTypeId": 1,
            #         "accountTypeName": "SAVING ACCOUNT",
            #         "branchName": "Nepal Mega Bank Ltd. -Pulchowk Branch",
            #         "id": 1231234
            #     }
            # ]
            branch_info = r.json()[0]
            branch_info['bankId'] = bank['id']
            self.branch_info = branch_info
        else:
            raise ValueError("Unable to fetch banks for user: '%s'" % self.account.user)

    def bank_info(self):
        r = requests.get('https://webbackend.cdsc.com.np/api/meroShare/bank/',
                         headers=self.authorization_headers,
                         verify=False)
        if r.ok:
            banks = r.json()
            if len(banks) == 0:
                raise ValueError("No banks found for user: '%s'" % self.account.user)

            return banks[0]
        else:
            raise ValueError("Unable to fetch banks for user: '%s'" % self.account.user)

    @property
    def demat(self):
        return f"130{self.account.dp}{self.account.username}"

    @property
    def authorization_headers(self):
        return {
            'Authorization': self.authorization
        }

    def can_apply(self, company_share_id):
        response = requests.get(
            f"https://webbackend.cdsc.com.np/api/meroShare/applicantForm/customerType/{company_share_id}/{self.demat}",
            headers=self.authorization_headers, verify=False).json()

        return True if response['message'] == "Customer can apply." else False

    def apply(self, number_of_shares, company_share_id):
        issues = self.open_issues()
        issue = next(
            (item for item in issues if item.is_unapplied_ordinary_share and item.company_share_id == company_share_id),
            None
        )

        if not issue:
            raise ValueError(f"UNAPPLIED ISSUE NOT FOUND!! -- {company_share_id}")

        if not self.can_apply(company_share_id):
            print(f"CANNOT APPLY!! -- {company_share_id}")
            return

        payload = {
            "demat": self.demat,
            "boid": self.account.username,
            "accountNumber": self.branch_info['accountNumber'],
            "customerId": self.branch_info['id'],
            "accountBranchId": self.branch_info['accountBranchId'],
            "accountTypeId": self.branch_info['accountTypeId'],
            "appliedKitta": str(number_of_shares),
            "crnNumber": self.account.crn,
            "transactionPIN": self.account.pin,
            "companyShareId": str(company_share_id),
            "bankId": self.branch_info['bankId']
        }

        r = requests.post('https://webbackend.cdsc.com.np/api/meroShare/applicantForm/share/apply',
                          json=payload,
                          headers=self.authorization_headers,
                          verify=False)

        if r.ok:
            print(f"APPLIED SUCCESSFULLY!! -- {company_share_id}")
        else:
            print(f"APPLY UNSUCCESSFUL!! -- {company_share_id}")

    @cache
    def open_issues(self):
        payload = {
            "filterFieldParams": [
                {
                    "key": "companyIssue.companyISIN.script",
                    "alias": "Scrip"
                },
                {
                    "key": "companyIssue.companyISIN.company.name",
                    "alias": "Company Name"
                },
                {
                    "key": "companyIssue.assignedToClient.name",
                    "value": "",
                    "alias": "Issue Manager"
                }
            ],
            "filterDateParams": [
                {
                    "key": "minIssueOpenDate",
                    "condition": "",
                    "alias": "",
                    "value": ""
                },
                {
                    "key": "maxIssueCloseDate",
                    "condition": "",
                    "alias": "",
                    "value": ""
                }
            ],
            "page": 1,
            "size": 20,
            "searchRoleViewConstants": "VIEW_APPLICABLE_SHARE"
        }

        r = requests.post('https://webbackend.cdsc.com.np/api/meroShare/companyShare/applicableIssue/',
                          json=payload, headers=self.authorization_headers, verify=False)
        if globals().get('args') and getattr(args, 'debug', False):
            try:
                print('=== OPEN ISSUES RESPONSE ===')
                print('Status:', r.status_code)
                print(r.text)
            except Exception:
                pass
        if r.ok:
            objects = r.json()['object']
            return [Issue(_item) for _item in objects]
        else:
            raise ValueError("Error while getting open issues!!")

    def generate_reports(self):
        today = date.today()
        # Calculate two months ago, handling year wrap-around and month length
        month = today.month - 2
        year = today.year
        while month <= 0:
            month += 12
            year -= 1
        last_day = calendar.monthrange(year, month)[1]
        day = min(today.day, last_day)
        two_months_ago = date(year, month, day)
        payload = {
            "filterFieldParams": [
                {
                    "key": "companyShare.companyIssue.companyISIN.script",
                    "alias": "Scrip"
                },
                {
                    "key": "companyShare.companyIssue.companyISIN.company.name",
                    "alias": "Company Name"
                }
            ],
            "page": 1,
            "size": 20,
            "searchRoleViewConstants": "VIEW_APPLICANT_FORM_COMPLETE",
            "filterDateParams": [
                {
                    "key": "appliedDate",
                    "condition": "",
                    "alias": "",
                    "value": f"BETWEEN '{two_months_ago}' AND '{today}'"
                }
            ]
        }

        r = requests.post('https://webbackend.cdsc.com.np/api/meroShare/applicantForm/active/search/',
                          json=payload, headers=self.authorization_headers)
        if globals().get('args') and getattr(args, 'debug', False):
            try:
                print('=== GENERATE REPORTS RESPONSE ===')
                print('Status:', r.status_code)
                print(r.text)
            except Exception:
                pass
        if r.ok:
            objects = r.json()['object']
            return [self.with_allotment_status(_item) for _item in objects]
        else:
            raise ValueError("Error while fetching application reports!!")

    def with_allotment_status(self, _item):
        application_id = _item['applicantFormId']
        if _item['statusName'] in ['TRANSACTION_SUCCESS', 'APPROVED']:
            r = requests.get(
                f"https://webbackend.cdsc.com.np/api/meroShare/applicantForm/report/detail/{application_id}",
                headers=self.authorization_headers,
                verify=False)
            if r.ok:
                allotment_status = r.json()['statusName']
                _item['allotmentStatus'] = allotment_status
            else:
                raise ValueError("Error while fetching application allotment status!!")
        else:
            _item['allotmentStatus'] = 'N/A'

        return _item


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="""MeroShare simplified for bulk actions.
    - Find currently open issues
    - Check issue status (applied, unapplied, allotted or not-allotted)"""
    )

    parser.add_argument('-r', '--report', action='store_true', help='Check IPO allotment reports')
    parser.add_argument('-a', '--apply', action='store_true', help='Apply to issues', default=False)
    name_arg = parser.add_argument('-u', '--user',
                                   help='Run script for this user only, default is run for all users in accounts.csv '
                                        'file')
    share_id_arg = parser.add_argument('-c', '--company-share-id',
                                       help='Company share ID to apply, required when -a/--apply flag is set', type=int)
    parser.add_argument('-n', '--number-of-shares', help='Number of shares to apply, default is 10', default=10)
    parser.add_argument('-I', '--interactive', action='store_true', help='Run in interactive mode')
    parser.add_argument('-D', '--debug', action='store_true', help='Print raw issue JSON for debugging')
    args = parser.parse_args()

    accounts = find_accounts_from_csv(args.user)

    def safe_create_user_session(account):
        try:
            return UserSession(account=account)
        except ValueError as e:
            raw = str(e)
            server_msg = _extract_server_message(raw) or raw
            print(f"\033[31mError: {server_msg}\033[0m")
            return None

    def prompt_select_accounts(all_accounts):
        print("Available accounts:")
        for i, a in enumerate(all_accounts, start=1):
            print(f"  {i}. {a.user}")
        print("  0. All accounts")
        sel = input("Select account numbers (comma separated), or 0 for all: ").strip()
        if sel == '0':
            return all_accounts
        indices = []
        try:
            indices = [int(x.strip()) for x in sel.split(',') if x.strip()]
        except Exception:
            print("Invalid selection")
            return []
        chosen = [all_accounts[i-1] for i in indices if 1 <= i <= len(all_accounts)]
        return chosen

    def prompt_select_issue_from_user(u: UserSession):
        issues = u.open_issues()
        if not issues:
            print("No open issues found")
            return None
        for i, iss in enumerate(issues, start=1):
            print(f"  {i}. {iss.company_name} ({iss.scrip}) - id={iss.company_share_id}")
        sel = input("Select issue number to apply or press Enter to cancel: ").strip()
        if not sel:
            return None
        try:
            idx = int(sel)
            if 1 <= idx <= len(issues):
                return issues[idx-1].company_share_id
        except Exception:
            print("Invalid selection")
        return None

    def interactive_main(all_accounts):
        while True:
            print('\nInteractive menu:')
            print('  1. View open issues for an account')
            print('  2. Generate reports for an account')
            print('  3. Apply to an issue for a single account')
            print('  4. Bulk apply across accounts (same companyShareId)')
            print('  5. Exit')
            choice = input('Choose an option: ').strip()
            if choice == '1':
                chosen = prompt_select_accounts(all_accounts)
                if not chosen:
                    continue
                for acc in chosen:
                    print(f"=========  %s  =========" % acc.user.capitalize())
                    user = safe_create_user_session(acc)
                    if not user:
                        continue
                    issues = user.open_issues()
                    for iss in issues:
                        print(iss)
                        if args.debug:
                            print(json.dumps(iss._json_data, indent=2))
            elif choice == '2':
                chosen = prompt_select_accounts(all_accounts)
                if not chosen:
                    continue
                for acc in chosen:
                    print(f"=========  %s  =========" % acc.user.capitalize())
                    user = safe_create_user_session(acc)
                    if not user:
                        continue
                    report = user.generate_reports()
                    for item in report:
                        print(f"{item['companyName']} - {item.get('allotmentStatus', 'N/A')}")
            elif choice == '3':
                chosen = prompt_select_accounts(all_accounts)
                if not chosen or len(chosen) != 1:
                    print('Please select exactly one account for single-account apply')
                    continue
                acc = chosen[0]
                print(f"=========  %s  =========" % acc.user.capitalize())
                user = safe_create_user_session(acc)
                if not user:
                    continue
                csid = prompt_select_issue_from_user(user)
                if not csid:
                    continue
                num = input('Number of shares to apply (default 10): ').strip() or '10'
                try:
                    num = int(num)
                except Exception:
                    print('Invalid number')
                    continue
                confirm = input(f'Apply {num} shares to {csid} for {acc.user}? (y/N): ').strip().lower()
                if confirm == 'y':
                    user.apply(num, company_share_id=csid)
            elif choice == '4':
                chosen = prompt_select_accounts(all_accounts)
                if not chosen:
                    continue
                csid_in = input('Enter companyShareId to apply across selected accounts: ').strip()
                try:
                    csid = int(csid_in)
                except Exception:
                    print('Invalid companyShareId')
                    continue
                num = input('Number of shares to apply (default 10): ').strip() or '10'
                try:
                    num = int(num)
                except Exception:
                    print('Invalid number')
                    continue
                confirm = input(f'Apply {num} shares to {csid} for {len(chosen)} accounts? (y/N): ').strip().lower()
                if confirm != 'y':
                    continue
                for acc in chosen:
                    print(f"=========  %s  =========" % acc.user.capitalize())
                    user = safe_create_user_session(acc)
                    if not user:
                        continue
                    user.apply(num, company_share_id=csid)
            elif choice == '5':
                print('Exiting')
                break
            else:
                print('Invalid choice')

    # Determine whether to run interactive: explicit flag OR no action flags supplied
    run_interactive = args.interactive or not (args.report or args.apply or args.company_share_id or args.user)

    if run_interactive:
        interactive_main(accounts)
    else:
        for account in accounts:
            print(f"=========  %s  =========" % account.user.capitalize())

            user = safe_create_user_session(account)
            if not user:
                continue

            if args.report:
                report = user.generate_reports()
                for item in report:
                    print(f"{item['companyName']} - {item['allotmentStatus']}")
            elif args.apply:
                if not args.company_share_id:
                    raise argparse.ArgumentError(share_id_arg, "is required when -a/--apply flag is set, run the "
                                                       "script without any args to find the open issues with "
                                                       "their company share id")
                user.apply(int(args.number_of_shares), company_share_id=args.company_share_id)
            else:
                open_issues = user.open_issues()
                for iss in open_issues:
                    print(iss)
                    if args.debug:
                        print(json.dumps(iss._json_data, indent=2))
