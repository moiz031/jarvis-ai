$TargetFile = "$PSScriptRoot\dist\JarvisAI\JarvisAI.exe"
$ShortcutFile = "$env:USERPROFILE\Desktop\Jarvis AI.lnk"
$WScriptShell = New-Object -ComObject WScript.Shell
$Shortcut = $WScriptShell.CreateShortcut($ShortcutFile)
$Shortcut.TargetPath = $TargetFile
$Shortcut.WorkingDirectory = "$PSScriptRoot\dist"
$Shortcut.IconLocation = "$TargetFile,0"
$Shortcut.Description = "Launch JARVIS AI"
$Shortcut.Save()
Write-Host "Shortcut created at $ShortcutFile"
