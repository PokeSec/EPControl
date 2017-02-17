@echo off
rem build.py : Build a Windows EPControl agent package
rem
rem This file is part of EPControl.
rem
rem Copyright (C) 2016  Jean-Baptiste Galet & Timothe Aeberhardt
rem
rem EPControl is free software: you can redistribute it and/or modify
rem it under the terms of the GNU General Public License as published by
rem the Free Software Foundation, either version 3 of the License, or
rem (at your option) any later version.
rem
rem EPControl is distributed in the hope that it will be useful,
rem but WITHOUT ANY WARRANTY; without even the implied warranty of
rem MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
rem GNU General Public License for more details.
rem
rem You should have received a copy of the GNU General Public License
rem along with EPControl.  If not, see <http://www.gnu.org/licenses/>.
rem

setlocal
set dir=%~dp0
set arch="%~1

set VSTOOLS=%VS140COMNTOOLS%
if "%VSTOOLS%"=="" set VSTOOLS=%VS120COMNTOOLS%
if "%VSTOOLS%"=="" set VSTOOLS=%VS110COMNTOOLS%
if "%VSTOOLS%"=="" set VSTOOLS=%VS100COMNTOOLS%

echo "Setup environment for VS - %arch%"
if "%platf%"=="x64" (
    call "%VSTOOLS%..\..\VC\vcvarsall.bat" amd64 >nul
) else (
    call "%VSTOOLS%..\..\VC\vcvarsall.bat" x86_amd64 >nul
)

C:\Python35\python.exe "%dir%build.py" %*
