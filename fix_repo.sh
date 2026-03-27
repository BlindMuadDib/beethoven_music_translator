#!/bin/bash
set -e

echo "================================================="
echo "   Music Translator - Git Repo Fix & Sync Tool   "
echo "================================================="

echo "[1/5] Removing messy local history and massive files..."
# The previous 5 local commits contain huge files (like virtual environments and audio files).
# This drops those commits from history entirely but leaves your local files totally intact.
git reset --soft origin/v0.5

echo "[2/5] Cleaning the git cache deeply..."
# Uncaching EVERYTHING and letting your new aggressive .gitignore filter everything correctly.
git rm -r --cached . >/dev/null 2>&1 || true
git add .

echo "[3/5] Creating one clean commit..."
git commit -m "chore: clean up repo, establish version 0.1.4, fix CI paths and gitignore" || true

echo "[4/5] Transitioning to main branch..."
# We rename this working branch directly to main
git branch -D main 2>/dev/null || true
git branch -m main
git tag -f v0.1.4

echo "[5/5] Force pushing clean state directly to GitHub..."
# Since remote main is going to be completely overwritten, this fast and clean commit will take over!
git push -u origin main --force
git push origin v0.1.4 --force

echo "================================================="
echo "Done! The massive files were successfully skipped and main has been fully overwritten."
