# Reword all commits from a base ref using Conventional Commit messages (pick + exec amend).
# Usage: .\scripts\tools\git-reword-messages.ps1 -Base origin/main -MessagesFile path\to\messages.txt
param(
    [string]$Base = "origin/main",
    [Parameter(Mandatory = $true)]
    [string]$MessagesFile
)

$ErrorActionPreference = "Stop"
$messages = @(Get-Content $MessagesFile -Encoding ASCII | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" })
if ($messages.Count -eq 0) { throw "No messages in $MessagesFile" }

$commits = @(git rev-list --reverse "$Base..HEAD")
if ($commits.Count -ne $messages.Count) {
    throw "Expected $($commits.Count) commits from $Base..HEAD but messages file has $($messages.Count) entries"
}

$todo = @()
for ($i = 0; $i -lt $commits.Count; $i++) {
    $subject = git log -1 "--format=%s" $commits[$i]
    $msg = $messages[$i] -replace '"', '\"'
    if ($i -gt 0) {
        $todo += "pick $($commits[$i]) $subject"
    } else {
        $todo += "pick $($commits[$i]) $subject"
    }
    $todo += "exec git commit --amend -m `"$msg`""
}
$todo += ""

$todoPath = Join-Path $env:TEMP "git-reword-todo.txt"
$todo | Set-Content $todoPath -Encoding ASCII

$seqEditor = Join-Path $env:TEMP "git-reword-seq-from-file.ps1"
@'
param([string]$Path)
Copy-Item $env:REWORD_TODO_FILE $Path -Force
'@ | Set-Content $seqEditor -Encoding ASCII
$env:REWORD_TODO_FILE = $todoPath
$env:GIT_SEQUENCE_EDITOR = "powershell -NoProfile -ExecutionPolicy Bypass -File `"$seqEditor`""
Remove-Item Env:GIT_EDITOR -ErrorAction SilentlyContinue

git rebase -i $Base
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Remove-Item $todoPath, $seqEditor -ErrorAction SilentlyContinue
Remove-Item Env:REWORD_TODO_FILE -ErrorAction SilentlyContinue
Write-Host "Reworded $($commits.Count) commits on top of $Base"
