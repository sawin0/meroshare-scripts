## meroshare-scripts — Bulk IPO helper

Simple helper script to check open IPO issues, show per-account status, and bulk-apply for ordinary IPO shares.

**What it does:**

- Lists currently open (ordinary) IPO issues.
- Shows whether each account has already applied.
- Optionally applies to an IPO for all or selected accounts.
- Can generate IPO allotment reports.

## Prerequisites

- Python 3 (run `python3 --version`)
- Install dependencies: `pip3 install -r requirements.txt` (if any)
- Create `accounts.csv` using the provided `accounts.csv.example`.

## Quick help

Run the built-in help to see available flags and options:

```shell
python3 main.py --help
```

Typical usage (summary of flags):

- `-r, --report` : Generate IPO allotment reports.
- `-a, --apply` : Apply to an IPO (requires `-c`).
- `-u USER, --user USER` : Limit action to a single user from `accounts.csv`.
- `-c COMPANY_SHARE_ID, --company-share-id` : The target company share ID for applying.
- `-n NUMBER_OF_SHARES, --number-of-shares` : Number of shares to apply (default: 10).

## Examples

1. List open IPOs and check application status for all accounts:

```shell
python3 main.py
```

The script prints open issues and a `COMPANY SHARE ID` for each. Use that ID when applying.

2. Bulk apply the same IPO for all accounts (skips accounts that already applied):

```shell
python3 main.py -a -c 654 -n 10
```

3. Apply for a single user from `accounts.csv`:

```shell
python3 main.py -a -c 654 -n 10 -u ayerdines
```

4. Generate allotment reports for a single user:

```shell
python3 main.py -r -u ayerdines
```

5. Generate allotment reports for all users:

```shell
python3 main.py -r
```

## Notes & tips

- The script only handles **Ordinary IPO shares**.
- Ensure `accounts.csv` is present in the repository root and follows the example format.
- When applying, the `--company-share-id` value is required.
- Use `-u` to test actions on a single account before running bulk operations.

If you want, I can also: update `requirements.txt`, validate `accounts.csv` format, or add a short example `accounts.csv` to the repo.
