# Uploading this repository

Decisions already made: repository name **christos-reaction-prediction**,
**public**, licence **MIT** (see `LICENSE`).

What is left is a one-time authentication step that only the account owner can
do: GitHub needs a token or an SSH key, and neither is in this folder.

## Option A — personal access token (easiest)

1. GitHub → Settings → Developer settings → Personal access tokens →
   **Tokens (classic)** → Generate new token. Scope: `repo`.
2. Copy the token (starts with `ghp_`). Treat it as a password; do not paste it
   into a file inside this repository.

Then, from this folder:

```powershell
git remote add origin https://github.com/<your-account>/christos-reaction-prediction.git
git push -u origin master
# username: <your-account>
# password: <paste the token>
```

`git` will offer to remember the credential; on Windows the default helper
stores it in the Windows Credential Manager, which is fine.

## Option B — create the empty repository first, then push

If you prefer to create it in the browser: **New repository** → name
`christos-reaction-prediction` → **Public** → do **not** add a README, licence
or .gitignore (this folder already has them) → Create. Then run the two commands
above.

## Option C — SSH

```powershell
ssh-keygen -t ed25519 -C "your@email"
# add the public key at GitHub → Settings → SSH and GPG keys
git remote add origin git@github.com:<your-account>/christos-reaction-prediction.git
git push -u origin master
```

## What gets pushed

Branch `master`, 7 commits, about 83 MB of working tree. The repository history
here is fresh (created for release); the original development history was not
carried over because it contains a 1 GB data file that GitHub rejects.

## After pushing

- Add the URL and the commit hash to the paper's "Data and code availability"
  section, e.g.
  `https://github.com/<your-account>/christos-reaction-prediction (commit XXXXXXX)`.
- Optionally enable the **Zenodo** integration to get a DOI for the release;
  cite the DOI instead of a commit hash.
- Verify the clone works on a machine without your data:

```powershell
git clone https://github.com/<your-account>/christos-reaction-prediction
cd christos-reaction-prediction
python -I tools/validate_tcm_on_subset.py   # TCM cases against the bundled subset
python -I tools/check_template_leakage.py   # leakage check, about 30 s
```
