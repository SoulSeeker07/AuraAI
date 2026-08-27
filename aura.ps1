# AuraAI PowerShell Launcher
param(
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$ArgsList
)

$AURA_DIR = "D:\Sreekanta\VS Code Project\Desktop AI\AuraAI"
$PY = "$AURA_DIR\.venv\Scripts\python.exe"

if ($ArgsList.Count -eq 0 -or $ArgsList[0] -in @("notch", "--notch", "voice", "--voice")) {
    & $PY "$AURA_DIR\run_voice_notch.py"
} elseif ($ArgsList[0] -in @("gui", "--gui", "main", "--main")) {
    & $PY "$AURA_DIR\main.py" --gui
} elseif ($ArgsList[0] -in @("chat", "--chat")) {
    & $PY "$AURA_DIR\run_chat_window.py"
} else {
    & $PY "$AURA_DIR\main.py" @ArgsList
}
