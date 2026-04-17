Dim fso, sh, scriptDir, batPath
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
batPath = scriptDir & "\start_loop_py_background.bat"

If fso.FileExists(batPath) Then
  sh.Run Chr(34) & batPath & Chr(34), 0, False
End If
