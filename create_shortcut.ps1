$TargetFile = "$PSScriptRoot\dist\Jarvis_Mark_VII.exe"
$ShortcutFile = "$env:USERPROFILE\Desktop\Jarvis AI.lnk"
$WScriptShell = New-Object -ComObject WScript.Shell
$Shortcut = $WScriptShell.CreateShortcut($ShortcutFile)
$Shortcut.TargetPath = $TargetFile
$Shortcut.WorkingDirectory = "$PSScriptRoot\dist"
$Shortcut.IconLocation = "$TargetFile,0"
$Shortcut.Description = "Launch JARVIS Omni-Perception Mark VII"
$Shortcut.Save()
Write-Host "Shortcut created at $ShortcutFile"
