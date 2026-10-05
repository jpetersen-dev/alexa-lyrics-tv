' Alexa Lyrics TV - Lanzador silencioso en segundo plano
' Ejecuta el servidor uvicorn sin abrir ventana de consola visible

Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
projectDir = fso.GetParentFolderName(scriptDir)

pythonExe = projectDir & "\.venv\Scripts\python.exe"

If Not fso.FileExists(pythonExe) Then
    MsgBox "No se encontro el interprete Python en: " & pythonExe, vbCritical, "Alexa Lyrics TV"
    WScript.Quit 1
End If

cmd = """" & pythonExe & """ -m uvicorn src.server:app --host 0.0.0.0 --port 8000"

WshShell.CurrentDirectory = projectDir
' El segundo argumento 0 oculta totalmente la ventana de consola
WshShell.Run cmd, 0, False
