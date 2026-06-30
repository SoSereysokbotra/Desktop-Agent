$startup = [Environment]::GetFolderPath('Startup')
$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut("$startup\Desktop Agent.lnk")
$shortcut.TargetPath = 'D:\Year2\AI_Engineering\agent_v3\start_agent.bat'
$shortcut.WorkingDirectory = 'D:\Year2\AI_Engineering\agent_v3'
$shortcut.Description = 'Desktop Agent Autostart'
$shortcut.Save()
Write-Host "Shortcut created at: $startup\Desktop Agent.lnk"
