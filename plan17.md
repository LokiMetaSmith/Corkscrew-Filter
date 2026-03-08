If `content.replace("divSchemes\n{", ...)` didn't match, maybe the file uses `\r\n` line endings!
Ah! In Windows (which the user is using: `C:\Users\Loki-VR\...`), Git often checks out files with CRLF (`\r\n`) line endings!
So `content.replace("divSchemes\n{", ...)` will FAIL to match `divSchemes\r\n{`!

Let's verify this theory by reading the file with `repr()`.
