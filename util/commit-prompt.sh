#!/usr/bin/env bash
#
# commit-prompt.sh
# Builds an AI prompt to suggest a conventional commit message based on
# staged changes and copies it to the clipboard.
#
# Usage:
#   bash util/commit-prompt.sh
#   bash util/commit-prompt.sh --help

set -euo pipefail

MAX_DIFF_SIZE=15000

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

usage() {
  echo ""
  echo -e "${GREEN}commit-prompt.sh${NC} — Generates a commit prompt for an LLM."
  echo ""
  echo -e "${YELLOW}Usage:${NC}"
  echo "  bash util/commit-prompt.sh [options]"
  echo ""
  echo -e "${YELLOW}Options:${NC}"
  echo "  --help, -h    Show this help and exit."
  echo ""
  echo -e "${YELLOW}Prerequisites:${NC}"
  echo "  At least one staged file (git add <file>)."
  echo ""
  echo -e "${YELLOW}Clipboard compatibility:${NC}"
  echo "  macOS         pbcopy"
  echo "  Linux (X11)   xclip or xsel"
  echo "  None          Prints the prompt to stdout"
  echo ""
  echo -e "${YELLOW}Examples:${NC}"
  echo "  git add src/grid/engine.py && bash util/commit-prompt.sh"
  echo ""
}

# ── Flags ──────────────────────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h) usage; exit 0 ;;
    *)         echo -e "${RED}✗ Unknown argument: $1${NC}" >&2; exit 1 ;;
  esac
done

# ── Staged changes ─────────────────────────────────────────────────────────────

if git diff --cached --quiet; then
  echo -e "${RED}✗ No staged changes found.${NC}"
  echo -e "  Run ${YELLOW}git add <file>${NC} before executing this script."
  exit 1
fi

# ── Commit types ───────────────────────────────────────────────────────────────

TIPOS_LIST="\
  feat     — New feature or capability.
  fix      — Bug fix.
  perf     — Performance improvement.
  refactor — Code change that neither fixes a bug nor adds a feature.
  test     — Adding or correcting tests.
  docs     — Documentation changes only.
  style    — Formatting, whitespace — no functional impact.
  build    — Build system or dependency changes.
  ci       — CI/CD configuration changes.
  revert   — Revert a previous commit.
  chore    — Maintenance tasks that don't fit other types."

ASSUNTO_RULE="The subject must be a clear, concise description of what was done, \
starting with an imperative verb in lowercase (e.g. add, fix, remove, update)."

# ── Issue reference (detected from branch name) ────────────────────────────────

CURRENT_BRANCH=$(git symbolic-ref --short HEAD 2>/dev/null || echo "")
ISSUE_NUMBER=$(echo "$CURRENT_BRANCH" | grep -oE '/[0-9]+' | tr -d '/' | head -n1 || true)

ISSUE_NOTE=""
if [[ -n "$ISSUE_NUMBER" ]]; then
  ISSUE_NOTE="
Issue reference (optional):
If this commit closes or references an issue, append to the commit:

  git commit -m '<type>: <subject>' -m 'References: #${ISSUE_NUMBER}'

Issue detected in branch: #${ISSUE_NUMBER}"
fi

# ── Collect diff ───────────────────────────────────────────────────────────────

FILES=$(git diff --name-only --cached)
FILE_COUNT=$(echo "$FILES" | grep -c . || true)
DIFF=$(git diff --cached --unified=3)

DIFF_ORIGINAL_SIZE=${#DIFF}
if [[ $DIFF_ORIGINAL_SIZE -gt $MAX_DIFF_SIZE ]]; then
  DIFF="${DIFF:0:$MAX_DIFF_SIZE}"
  DIFF_TRUNCATED=" [diff truncated: $(( DIFF_ORIGINAL_SIZE - MAX_DIFF_SIZE )) characters omitted]"
else
  DIFF_TRUNCATED=""
fi

# ── Body instruction ───────────────────────────────────────────────────────────

if [[ "$FILE_COUNT" -gt 1 ]]; then
  BODY_INSTRUCTION='Multiple files are staged. Add a body summarising the most relevant changes
(max 5 bullets, one line each). Each bullet should start with the file or component
name followed by a brief description.

IMPORTANT — format:
- Write the command on a SINGLE LINE with no line breaks
- Use the $'"'"'...'"'"' syntax with \n to separate bullets inside the second -m
- Do not use backslash (\) to continue the command on another line'

  OUTPUT_FORMAT="git commit -m \"<type>: <subject>\" -m \$'- <summary 1>\\n- <summary 2>\\n- <summary 3>'"
else
  BODY_INSTRUCTION='Only one file is staged. Add a body with a rich description explaining:
what the problem or need was, what was changed, and why this approach was chosen.
Write 1 to 3 sentences, in English, clearly and technically. No bullets.

IMPORTANT — format:
- Write the command on a SINGLE LINE with no line breaks
- Use the $'"'"'...'"'"' syntax for the body
- Do not use backslash (\) to continue the command on another line'

  OUTPUT_FORMAT='git commit -m "<type>: <subject>" -m $'"'"'<rich description in 1–3 sentences>'"'"''
fi

# ── Build prompt ───────────────────────────────────────────────────────────────

PROMPT=$(cat <<EOF
You are a senior software engineer expert at writing clear, professional commit messages.

Generate a commit message in ENGLISH based on the changes below.
Follow the Conventional Commits specification strictly.

────────────────────────────────────────────────────────────
RULES
────────────────────────────────────────────────────────────

Required format:
  <type>: <subject>

Subject rule:
  ${ASSUNTO_RULE}

Valid types (use exactly one):
${TIPOS_LIST}

────────────────────────────────────────────────────────────
CONSTRAINTS
────────────────────────────────────────────────────────────

- Use ONLY the types listed above — do not invent others
- The subject must be entirely in lowercase
- The subject must start with an imperative verb (e.g. add, fix, remove, update, refactor)
- Maximum 72 characters on the commit subject line
- Do NOT use markdown, code blocks, or external explanations

────────────────────────────────────────────────────────────
EXPECTED OUTPUT
────────────────────────────────────────────────────────────

${BODY_INSTRUCTION}

Return ONLY the ready-to-run bash command:

  ${OUTPUT_FORMAT}
${ISSUE_NOTE}
────────────────────────────────────────────────────────────
STAGED CHANGES
────────────────────────────────────────────────────────────

Files:
${FILES}

Diff:${DIFF_TRUNCATED}
${DIFF}
EOF
)

# ── Copy to clipboard ──────────────────────────────────────────────────────────

if command -v pbcopy &>/dev/null; then
  echo "$PROMPT" | pbcopy
  CLIPBOARD_CMD="pbcopy"
elif command -v xclip &>/dev/null; then
  echo "$PROMPT" | xclip -selection clipboard
  CLIPBOARD_CMD="xclip"
elif command -v xsel &>/dev/null; then
  echo "$PROMPT" | xsel --clipboard --input
  CLIPBOARD_CMD="xsel"
elif command -v clip.exe &>/dev/null; then
  echo "$PROMPT" | clip.exe
  CLIPBOARD_CMD="clip.exe"
else
  echo -e "${YELLOW}⚠ No clipboard utility found (pbcopy, xclip, xsel, clip.exe).${NC}"
  echo -e "  Printing prompt below:\n"
  echo "$PROMPT"
  exit 0
fi

echo ""
echo -e "${GREEN}✓ Prompt copied to clipboard.${NC}"
echo ""
echo -e "  Paste it into an LLM to generate the commit command."
echo ""
