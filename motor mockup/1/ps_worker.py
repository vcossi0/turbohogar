"""
Worker que ejecuta UN JSX en Photoshop y sale.
Se llama como subprocess desde generador_mockups_v6.py.
Lee el JSX desde stdin, imprime resultado en stdout.
"""
import sys
import win32com.client
import pythoncom

pythoncom.CoInitialize()
ps = win32com.client.GetActiveObject("Photoshop.Application")
jsx_code = sys.stdin.buffer.read().decode("utf-8")
try:
    result = ps.DoJavaScript(jsx_code)
    sys.stdout.write(result if result else "OK")
except Exception as e:
    sys.stdout.write(f"ERROR:{e}")
