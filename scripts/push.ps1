param(
    [Parameter(Mandatory = $true, Position = 0, ValueFromRemainingArguments = $true)]
    [string[]]$Message
)

$ErrorActionPreference = "Stop"
git add -A
git commit -m ($Message -join ' ')
git push
