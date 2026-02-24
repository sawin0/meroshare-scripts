## meroshare-scripts — Bulk IPO helper

Simple helper script to check open IPO issues, show per-account status, and bulk-apply for ordinary IPO shares.

**What it does:**

- Lists currently open (ordinary) IPO issues.
- Shows whether each account has already applied.
- Optionally applies to an IPO for all or selected accounts.
- Can generate IPO allotment reports.

## Quick start (easy)

1. Install Python 3 if you don't already have it. Check with:

```bash
python3 --version
```

2. Install dependencies (if any are listed):

```bash
pip3 install -r requirements.txt
```

3. Create an `accounts.csv` file from the example file `accounts.csv.example` and fill in your account details.

4. Run the script. For most users the easiest is interactive mode (menu-driven):

```bash
python3 main.py
```

What the script can do (simple terms):

- Show currently open IPOs you can apply for.
- Tell you whether each of your accounts has already applied.
- Apply to an IPO for one or many accounts in bulk.
- Create a short report of IPO allotments (who got shares).

Common commands (copy & paste):

- Run interactive menu (recommended for non-technical users):

```bash
python3 main.py -I
```

- List open IPOs and see per-account status:

```bash
python3 main.py
```

- Apply the same IPO to all accounts (replace 654 with the COMPANY SHARE ID shown by the script):

```bash
python3 main.py -a -c 654 -n 10
```

- Apply for a single account only (replace USER with the `user` from your `accounts.csv`):

```bash
python3 main.py -a -c 654 -n 10 -u USER
```

- Get IPO allotment reports:

```bash
python3 main.py -r
```

Helpful flags:

- `-a` or `--apply`: apply to an IPO (you must also pass `-c`)
- `-c` or `--company-share-id`: the ID to apply to (the script prints this when listing issues)
- `-u` or `--user`: run the action for a single user from `accounts.csv`
- `-n` or `--number-of-shares`: number of shares to apply (default 10)
- `-I` or `--interactive`: open the menu-based interface
- `-D` or `--debug`: print more debugging info (advanced)

Safety & privacy (please read):

- The script reads credentials from `accounts.csv`. Keep that file private and do not commit it to public
  repositories.
- The script sends sensitive data (like PINs) to the remote server. Run it only on a trusted computer.
- For some network calls the script disables strict HTTPS verification to avoid certificate errors. This helps
  in some environments but is less secure — if you manage certificates, re-enable verification in `main.py`.

Need help? I can:

- Add a simple `accounts.csv` example with fake data.
- Check or pin packages in `requirements.txt`.
- Walk you through running the interactive menu step-by-step.
