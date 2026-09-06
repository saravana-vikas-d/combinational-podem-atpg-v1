# Git Workflow Instructions

Daily instructions for building the combinational PODEM ATPG project and keeping GitHub updated.

## Your Repo Setup

| Item | Value |
|---|---|
| **Local folder** | `/home/saravana/combinational-podem-atpg-v1` |
| **Current branch** | `main` |
| **Tracks** | `github/main` (GitHub is your default push target) |
| **GitHub repo** | https://github.com/saravana-vikas-d/combinational-podem-atpg-v1 |
| **Cursor repo** | https://origin.cursor.com/saravana-vikas/combinational-podem-atpg-v1 |

### How It's Connected

You have **two remotes** in one local repo:

```
Local machine  ──push/pull──►  github  ──►  GitHub (public backup / portfolio)
              ──push/pull──►  origin  ──►  Cursor-hosted copy (IDE backup)
```

- **`github`** → your GitHub repo (`saravana-vikas-d/combinational-podem-atpg-v1`)
- **`origin`** → Cursor's hosted copy (same project, different host)

Your `main` branch is set to track **`github/main`**, so a plain `git push` goes to **GitHub** by default. That's the right setup for daily work.

---

## Daily Workflow (Follow Every Coding Session)

### 1. Start of Day — Sync First

```bash
cd /home/saravana/combinational-podem-atpg-v1
git pull
```

If you ever work from another machine, this brings in anything you pushed earlier.

### 2. Build and Code

Create/edit files as usual. Check status anytime:

```bash
git status
```

### 3. End of a Logical Chunk — Commit

Stage only what you intend to save:

```bash
git add <files>          # or: git add .
git commit -m "Short message: what you did and why"
```

**Good commit messages:**

- `add netlist parser for ISCAS circuits`
- `implement PODEM backtrace for XOR gates`
- `fix fault activation for stuck-at-0`

Commit often — after each feature, fix, or milestone. Small commits are easier to review and revert.

### 4. Push to GitHub

```bash
git push
```

That pushes `main` → `github/main` automatically.

**Verify on GitHub:** open your repo page and confirm the latest commit appears.

### 5. Optional — Also Back Up to Cursor

```bash
git push origin main
```

Only needed if you want the Cursor-hosted copy in sync. GitHub is your main remote for this workflow.

---

## Recommended Habits While Building

1. **Pull before you start** — avoids conflicts if you switched machines.
2. **Commit at least once per session** — don't leave a full day of work uncommitted.
3. **Push at end of session** — so GitHub always has your latest work.
4. **One feature per commit** — easier to understand history later.
5. **Don't commit secrets** — no API keys, passwords, or `.env` with credentials.
6. **Use branches for experiments** (optional but good practice):

```bash
git checkout -b feature/podem-core    # work on a feature
git add .
git commit -m "implement PODEM recursion"
git push -u github feature/podem-core # push branch to GitHub
```

Merge into `main` on GitHub (Pull Request) or locally when the feature works.

---

## Quick Reference Card

```bash
# Start of day
git pull

# After coding
git status
git add .
git commit -m "describe your change"
git push                    # → GitHub (default)

# Optional Cursor backup
git push origin main
```

---

## If Something Goes Wrong

| Problem | Fix |
|---|---|
| `git push` rejected (remote has new commits) | `git pull` → resolve conflicts → `git push` |
| Pushed to wrong remote | Use `git push github main` explicitly |
| Want to see remotes | `git remote -v` |
| Want to see history | `git log --oneline` |

---

## Bottom Line

Code locally → `git add` → `git commit` → `git push`. Because `main` tracks `github/main`, GitHub stays updated with almost no extra steps.
