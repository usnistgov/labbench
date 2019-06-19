@ECHO ON 

call "%userprofile%\AppData\Local\Continuum\Anaconda2\Scripts\activate.bat"
call "%userprofile%\AppData\Local\Continuum\Anaconda2\Scripts\activate.bat" py36
call "C:\ProgramData\Anaconda2\Scripts\activate.bat"
call "C:\ProgramData\Anaconda2\Scripts\activate.bat" py36

del /Q /S _temp html rst
sphinx-apidoc -F .. -o .
sphinx-build -b html . ../public

pause