#Requires -Version 5.1
<#
.SYNOPSIS
    Builds an AI prompt to suggest a conventional commit message based on
    staged changes and copies it to the clipboard.

.EXAMPLE
    .\util\commit-prompt.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$MAX_DIFF_SIZE = 15000

# ── Staged changes ─────────────────────────────────────────────────────────────

git diff --cached --quiet 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host 'x No staged changes found.' -ForegroundColor Red
    Write-Host '  Run git add <file> before executing this script.'
    exit 1
}

# ── Commit types ───────────────────────────────────────────────────────────────

$TIPOS_LIST = @'
  feat     - New feature or capability.
  fix      - Bug fix.
  perf     - Performance improvement.
  refactor - Code change that neither fixes a bug nor adds a feature.
  test     - Adding or correcting tests.
  docs     - Documentation changes only.
  style    - Formatting, whitespace - no functional impact.
  build    - Build system or dependency changes.
  ci       - CI/CD configuration changes.
  revert   - Revert a previous commit.
  chore    - Maintenance tasks that don't fit other types.
'@

$ASSUNTO_RULE = 'The subject must be a clear, concise description of what was done, starting with an imperative verb in lowercase (e.g. add, fix, remove, update).'

# ── Issue reference (detected from branch name) ────────────────────────────────

$currentBranch = git symbolic-ref --short HEAD 2>$null
$issueMatch = [regex]::Match(($currentBranch -join ''), '/(\d+)')
$ISSUE_NOTE = ''
if ($issueMatch.Success) {
    $issueNumber = $issueMatch.Groups[1].Value
    $ISSUE_NOTE = ("`n" +
        "Issue reference (optional):`n" +
        "If this commit closes or references an issue, append:`n`n" +
        "  git commit -m '<type>: <subject>' -m 'References: #$issueNumber'`n`n" +
        "Issue detected in branch: #$issueNumber`n")
}

# ── Collect diff ───────────────────────────────────────────────────────────────

$FILES      = (git diff --name-only --cached) -join "`n"
$FILE_COUNT = (git diff --name-only --cached).Count
$DIFF       = (git diff --cached --unified=3) -join "`n"

$DIFF_TRUNCATED = ''
if ($DIFF.Length -gt $MAX_DIFF_SIZE) {
    $omitted        = $DIFF.Length - $MAX_DIFF_SIZE
    $DIFF           = $DIFF.Substring(0, $MAX_DIFF_SIZE)
    $DIFF_TRUNCATED = " [diff truncated: $omitted characters omitted]"
}

# ── Body instruction ───────────────────────────────────────────────────────────

if ($FILE_COUNT -gt 1) {
    $BODY_INSTRUCTION = @'
Multiple files are staged. Add a body summarising the most relevant changes
(max 5 bullets, one line each). Each bullet should start with the file or component
name followed by a brief description.

IMPORTANT - format:
- Write the command on a SINGLE LINE with no line breaks
- Use the $'...' syntax with \n to separate bullets inside the second -m
- Do not use backslash (\) to continue the command on another line
'@
    $OUTPUT_FORMAT = "git commit -m `"<type>: <subject>`" -m `$'- <summary 1>\n- <summary 2>\n- <summary 3>'"
} else {
    $BODY_INSTRUCTION = @'
Only one file is staged. Add a body with a rich description explaining:
what the problem or need was, what was changed, and why this approach was chosen.
Write 1 to 3 sentences, in English, clearly and technically. No bullets.

IMPORTANT - format:
- Write the command on a SINGLE LINE with no line breaks
- Use the $'...' syntax for the body
- Do not use backslash (\) to continue the command on another line
'@
    $OUTPUT_FORMAT = "git commit -m `"<type>: <subject>`" -m `$'<rich description in 1-3 sentences>'"
}

# ── Build prompt (via concatenation to avoid here-string issues with diff) ──────

$SEP = '────────────────────────────────────────────────────────────'

$PROMPT = (
    "You are a senior software engineer expert at writing clear, professional commit messages.`n`n" +
    "Generate a commit message in ENGLISH based on the changes below.`n" +
    "Follow the Conventional Commits specification strictly.`n`n" +
    "$SEP`n" +
    "RULES`n" +
    "$SEP`n`n" +
    "Required format:`n" +
    "  <type>: <subject>`n`n" +
    "Subject rule:`n" +
    "  $ASSUNTO_RULE`n`n" +
    "Valid types (use exactly one):`n" +
    "$TIPOS_LIST`n" +
    "$SEP`n" +
    "CONSTRAINTS`n" +
    "$SEP`n`n" +
    "- Use ONLY the types listed above - do not invent others`n" +
    "- The subject must be entirely in lowercase`n" +
    "- The subject must start with an imperative verb (e.g. add, fix, remove, update, refactor)`n" +
    "- Maximum 72 characters on the commit subject line`n" +
    "- Do NOT use markdown, code blocks, or external explanations`n`n" +
    "$SEP`n" +
    "EXPECTED OUTPUT`n" +
    "$SEP`n`n" +
    "$BODY_INSTRUCTION`n`n" +
    "Return ONLY the ready-to-run bash command:`n`n" +
    "  $OUTPUT_FORMAT`n" +
    "$ISSUE_NOTE" +
    "$SEP`n" +
    "STAGED CHANGES`n" +
    "$SEP`n`n" +
    "Files:`n" +
    "$FILES`n`n" +
    "Diff:$DIFF_TRUNCATED`n" +
    $DIFF
)

# ── Copy to clipboard ──────────────────────────────────────────────────────────

Set-Clipboard -Value $PROMPT

Write-Host ''
Write-Host 'v Prompt copied to clipboard.' -ForegroundColor Green
Write-Host ''
Write-Host '  Paste it into an LLM to generate the commit command.'
Write-Host ''
