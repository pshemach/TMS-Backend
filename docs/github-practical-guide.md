# How GitHub works in practice

This guide uses this repository (`TMS-Backend`) and the merge you just did.
The branches are `main` and `restructure`. The files are `main.py` and `.env.example`.

## 1. The three places your code lives

GitHub work always involves three copies. Mixing them up is what made the refresh show the old files.

| Place | What it is | In your case |
|---|---|---|
| Working folder | The files open in Cursor on your PC | `C:\Users\HP\...\TMS-Backend` |
| Local branch | The Git history saved on your PC | `restructure` at commit `dd07035` |
| GitHub branch | The copy on github.com | `origin/main` and `origin/restructure` |

Editing a file changes only the working folder.
A **commit** saves that edit onto the local branch.
A **push** uploads that commit to GitHub.
A **pull** (or the refresh you did) downloads GitHub's commits onto your PC.

Until you push, GitHub does not know about your edit.
Until you pull, your PC does not know about a merge someone finished on the website.

## 2. What a branch is

A branch is a named line of commits.

- `main` is the shared line. After your last fix, this is the good copy: short `main.py`, and `.env.example` with `DATABASE_URL`, `SOLVER_TIME_LIMIT_SECONDS`, and `OSRM_BASE_URL`.
- `restructure` is the line you were building the new layout on. It still has the mixed `main.py` from the conflict resolution.

Commits on one branch do not appear on the other branch until you merge.

That is why this happened:

1. Conflict resolution was committed on `restructure`.
2. A few minutes later, `update main for working` fixed both files on `main` only.
3. Refreshing `restructure` downloaded `restructure`. It did not download the fix, because that fix is a commit on `main`.

## 3. The everyday loop

Use this every time you change code.

```text
1. git checkout restructure          # work on your branch, not on main
2. edit files
3. git add main.py .env.example
4. git commit -m "why you changed it"
5. git push
6. open a Pull Request on GitHub: restructure -> main
7. wait until checks look right, then merge the Pull Request
8. git checkout main
9. git pull                          # your PC's main now matches GitHub
```

Do the new work on `restructure` (or a new branch), then open a Pull Request into `main`.
Do not edit `main` on the website and `restructure` on your PC at the same time. That is what created two different versions of the same file.

## 4. What a Pull Request actually does

A Pull Request is a proposal: "please add the commits from `restructure` onto `main`."

GitHub compares the two tips:

- **Base** = the branch you want to update. For you, `main`.
- **Compare / head** = the branch that has the new work. For you, `restructure`.

If Git can combine the files by itself, the green **Merge** button works and you never see a conflict.

If both branches changed the same lines, Git stops and asks you to choose. That is a conflict. The merge is not finished until every conflict is resolved and the result is committed.

## 5. The screen you used, and what the buttons mean

Your conflict commit message is:

```text
Merge branch 'main' into restructure
```

Read that sentence as written. GitHub was copying **`main` into `restructure`** so the Pull Request could be updated. It was not yet copying `restructure` into `main`.

On that screen:

| Button | Branch it keeps | Your files |
|---|---|---|
| **Accept current** | `restructure` (the branch being updated) | The new short `main.py`, and `.env.example` with the database, solver, and OSRM lines |
| **Accept incoming** | `main` (the branch being brought in) | The old long `main.py`, and the older `.env.example` |
| **Accept both** | Pieces of each side, one after the other | Usually a broken file. Avoid this unless you mean to combine them by hand |

**Incoming** means "the other branch that is arriving."
In a "merge `main` into `restructure`" conflict, incoming is `main`.

You clicked **Accept incoming**, so Git kept `main`'s older text for each conflict block.

## 6. Why `main.py` became a mixture

Git does not always conflict the whole file. It conflicts only the lines both sides changed, and it keeps the lines that only one side changed.

Your `main.py` had two conflict blocks and a quiet middle:

```text
<<<<<<< current (restructure)
"""TMS Backend entrypoint."""
=======
from fastapi import FastAPI
... old imports ...
import uvicorn
>>>>>>> incoming (main)

import uvicorn
from src.api.app import app
__all__ = ["app"]

<<<<<<< current (restructure)
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
=======
app.include_router(...)
...
uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
>>>>>>> incoming (main)
```

**Accept incoming** on both blocks produced exactly the file you have now:

1. Old imports, from the first incoming block.
2. `from src.api.app import app` and `__all__`, because those lines were outside both blocks, so Git left them in place.
3. Old `include_router(...)` lines and `reload=True`, from the second incoming block.

The buttons replace one block. They do not replace the whole file.

For a file you rewrote from top to bottom, open the file and make it the version you want, then mark the conflict resolved. Do not click **Accept incoming** on each block and assume the rest of the file follows.

## 7. Why `.env.example` went backward

Both branches had created `.env.example`, with different contents. Git calls that an add/add conflict: there is no shared older copy to blend, so the whole file is one choice.

| Side | Contents |
|---|---|
| Current (`restructure`) | `DATABASE_URL`, `SOLVER_TIME_LIMIT_SECONDS`, `OSRM_BASE_URL`, plus the folder names |
| Incoming (`main`) | Folder names only, written as `CLIENT = 'common'` |

**Accept incoming** saved the older `main` file. The three new settings were dropped because they lived only on the current side.

## 8. What happened after you clicked resolve

In order:

1. `restructure` had the new `main.py` (commit `restructure code base and test cases added`).
2. On GitHub you resolved the conflict by taking incoming (`main`). GitHub committed that onto `restructure`.
3. Your local refresh merged that GitHub `restructure` into the `restructure` on your PC. The mixed files arrived with it.
4. Pull Request #2 then merged that `restructure` into `main`, so `main` received the mixed files too.
5. Commit `update main for working` repaired `main.py` and `.env.example` on `main` only.

`main` on GitHub is the repaired copy.
`restructure` on GitHub and on your PC is still the conflict result.
Refreshing `restructure` will keep showing the mixed files until `restructure` receives the repair commit.

## 9. How to put the good files back onto `restructure`

`main` already has the repaired files. Bring `main` into `restructure` and, if Git asks again, keep `main`'s copy of these two files.

```powershell
git checkout restructure
git fetch origin
git merge origin/main
```

If `main.py` or `.env.example` conflicts:

```powershell
git checkout --theirs main.py
git checkout --theirs .env.example
git add main.py .env.example
git commit -m "Take the repaired main.py and .env.example from main"
git push
```

During `git merge origin/main`, **theirs** is `origin/main`, because `main` is the branch being brought in.
**ours** is `restructure`, the branch you have checked out.

Check the files before you commit. `main.py` should be the short entrypoint:

```python
"""TMS Backend entrypoint."""

import uvicorn

from src.api.app import app

__all__ = ["app"]

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

`.env.example` should include `DATABASE_URL`, `SOLVER_TIME_LIMIT_SECONDS`, and `OSRM_BASE_URL`.

## 10. Rules that prevent the same result

1. Decide which branch owns the file before you merge. Here, the rewritten `main.py` belonged to `restructure`, so the conflict resolution needed **Accept current**.
2. Read the merge sentence. `Merge branch 'main' into restructure` means incoming = `main`.
3. After resolving, open the file. If you still see two styles of the same file stacked together, the resolution is incomplete.
4. A commit on `main` does not change `restructure`. Merge or rebase if the other branch should receive it.
5. Pull (refresh) the branch you are looking at. Refreshing `restructure` never shows a commit that exists only on `main`.
6. Push after a local merge. Until you push, GitHub still has the old branch.

## 11. Words you will see again

| Word | Practical meaning |
|---|---|
| Commit | A saved snapshot with a message |
| Push | Upload your commits to GitHub |
| Pull / fetch | Download GitHub's commits |
| Branch | One line of commits (`main`, `restructure`) |
| Merge | Join one branch's commits into another |
| Pull Request | A GitHub page for reviewing that join before it lands on `main` |
| Base | The branch that will receive the work (`main`) |
| Head | The branch that contains the work (`restructure`) |
| Conflict | Both branches edited the same lines; Git needs a decision |
| Current | The branch you are updating |
| Incoming | The other branch being merged in |
| origin | The GitHub remote, `https://github.com/pshemach/TMS-Backend.git` |
