[CmdletBinding()]
param(
    [switch]$SkipPath
)

$ErrorActionPreference = 'Stop'
$MinPython = [version]'3.11'

function Find-Python {
    $ErrorActionPreference = 'Continue'
    $candidates = @(
        @{ Exe = 'py'; Args = @('-3') },
        @{ Exe = 'python'; Args = @() }
    )
    foreach ($candidate in $candidates) {
        if (-not (Get-Command $candidate.Exe -ErrorAction SilentlyContinue)) { continue }
        $pyArgs = $candidate.Args
        $version = & $candidate.Exe @pyArgs -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $version -and ([version]$version -ge $MinPython)) {
            return $candidate
        }
    }
    return $null
}

function Get-PathWithEntry {
    param([string]$CurrentPath, [string]$Entry)
    $normalized = $Entry.TrimEnd('\')
    $parts = @($CurrentPath -split ';' | Where-Object { $_.Trim() })
    if ($parts | Where-Object { $_.Trim().TrimEnd('\') -ieq $normalized }) {
        return $null
    }
    return (@($parts) + $normalized) -join ';'
}

function Add-ToUserPath {
    param([string]$Entry)
    $current = (Get-Item 'HKCU:\Environment').GetValue('Path', '', 'DoNotExpandEnvironmentNames')
    $updated = Get-PathWithEntry -CurrentPath $current -Entry $Entry
    if ($null -eq $updated) {
        return $false
    }
    # ExpandString mantém as entradas com %VARIAVEIS% que já existiam no PATH.
    Set-ItemProperty -Path 'HKCU:\Environment' -Name 'Path' -Value $updated -Type ExpandString
    return $true
}

function Install-Ayan {
    $root = $PSScriptRoot
    Write-Host "A instalar o ayan em $root"

    $python = Find-Python
    if (-not $python) {
        throw "Não encontrei o Python $MinPython ou superior. Instala-o a partir de https://www.python.org/downloads/ e volta a correr este instalador."
    }

    $venvPython = Join-Path $root '.venv\Scripts\python.exe'
    if (-not (Test-Path $venvPython)) {
        Write-Host 'A criar o ambiente Python (.venv)...'
        $pyArgs = $python.Args
        & $python.Exe @pyArgs -m venv (Join-Path $root '.venv')
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao criar o .venv.' }
    }

    Write-Host 'A instalar as dependências...'
    & $venvPython -m pip install --quiet --disable-pip-version-check -r (Join-Path $root 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar as dependências.' }

    if ($SkipPath) {
        Write-Host 'PATH não alterado (-SkipPath).'
    }
    elseif (Add-ToUserPath -Entry $root) {
        # Também avisa o Windows da alteração, para que os novos terminais já vejam o PATH atualizado.
        [Environment]::SetEnvironmentVariable('AYAN_HOME', $root, 'User')
        $env:Path = "$env:Path;$root"
        Write-Host "Pasta adicionada ao PATH do utilizador: $root"
    }
    else {
        Write-Host 'A pasta já estava no PATH.'
    }

    Write-Host ''
    Write-Host 'Pronto. Abre um novo PowerShell e escreve: ayan'
}

if ($MyInvocation.InvocationName -ne '.') {
    Install-Ayan
}
