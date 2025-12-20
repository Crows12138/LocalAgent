Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "c:\Users\12916\Desktop\LocalAgent"
WshShell.Run "python api_server.py", 0, False
