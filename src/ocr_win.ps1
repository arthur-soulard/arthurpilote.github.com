# ocr_win.ps1 — OCR via le moteur integre a Windows (Windows.Media.Ocr).
#
# Aucune dependance externe, aucun binaire a embarquer, aucun acces reseau :
# le moteur fait partie de Windows 10/11 et tourne hors ligne.
#
# Appele par sante.py (captures FitDays), de deux facons :
#   powershell -NoProfile -ExecutionPolicy Bypass -File ocr_win.ps1
#              -ImagePath <png> -JsonPath <json>          (une image)
#   powershell ... -File ocr_win.ps1 -Serveur                (plusieurs)
# En -Serveur, le script ecrit "pret", puis lit sur l'entree une ligne
# "<image><TAB><json>" par image et repond "fait" quand le JSON est ecrit ;
# une ligne vide le termine. Demarrer PowerShell et charger le moteur coute
# environ 3 s, la lecture d'une image 0,3 s : un import en fait une dizaine
# (14/10/2026).
#
# Ecrit un JSON UTF-8 (sans BOM) :
#   {ok, lang, width, height, angle, words:[{t,l,x,y,w,h}]}
# Les positions sont indispensables : c'est elles qui permettent d'apparier
# un libelle a sa valeur sur la meme ligne, l'ordre de lecture du moteur
# n'etant pas fiable sur une mise en page en colonnes.

param(
    [string]$ImagePath,
    [string]$JsonPath,
    [switch]$Serveur
)

$ErrorActionPreference = "Stop"

function Write-Json($obj, $chemin) {
    $json = $obj | ConvertTo-Json -Depth 4 -Compress
    [System.IO.File]::WriteAllText($chemin, $json, (New-Object System.Text.UTF8Encoding $false))
}

function Repondre($texte) {
    [Console]::Out.WriteLine($texte)
    [Console]::Out.Flush()
}

try {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime

    # Passerelle IAsyncOperation -> Task, necessaire pour attendre les API WinRT
    $asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]

    function Await($task, $resultType) {
        $netTask = $asTaskGeneric.MakeGenericMethod($resultType).Invoke($null, @($task))
        $netTask.Wait(-1) | Out-Null
        $netTask.Result
    }

    [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime] | Out-Null
    [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime] | Out-Null
    [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null

    # Langue du profil utilisateur ; repli sur le francais puis l'anglais.
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
    if ($null -eq $engine) {
        foreach ($tag in @("fr-FR", "en-US")) {
            try {
                $lang = New-Object Windows.Globalization.Language $tag
                $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
                if ($null -ne $engine) { break }
            } catch { }
        }
    }
}
catch {
    if ($Serveur) { Repondre "ko" } else { Write-Json ([pscustomobject]@{ ok = $false; error = $_.Exception.Message }) $JsonPath }
    exit 0
}
if ($null -eq $engine) {
    if ($Serveur) { Repondre "ko no_engine" } else { Write-Json ([pscustomobject]@{ ok = $false; error = "no_engine" }) $JsonPath }
    exit 0
}

function Lire($image, $sortie) {
    try {
        $file    = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($image)) ([Windows.Storage.StorageFile])
        $stream  = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
        $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $bitmap  = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
        $result  = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
        $stream.Dispose()

        # `l` : numero de la ligne du moteur. Il separe deja deux colonnes de texte
        # et suit l'inclinaison d'une photo. Ajoute pour le module Vocabulaire
        # (retire en 4.4.0) ; sante.py ne s'en sert pas.
        $li = 0
        $words = foreach ($line in $result.Lines) {
            $li++
            foreach ($word in $line.Words) {
                [pscustomobject]@{
                    t = $word.Text
                    l = $li
                    x = [int]$word.BoundingRect.X
                    y = [int]$word.BoundingRect.Y
                    w = [int]$word.BoundingRect.Width
                    h = [int]$word.BoundingRect.Height
                }
            }
        }

        Write-Json ([pscustomobject]@{
            ok     = $true
            lang   = $engine.RecognizerLanguage.LanguageTag
            width  = $bitmap.PixelWidth
            height = $bitmap.PixelHeight
            angle  = $result.TextAngle
            words  = @($words)
        }) $sortie
    }
    catch {
        Write-Json ([pscustomobject]@{ ok = $false; error = $_.Exception.Message }) $sortie
    }
}

if ($Serveur) {
    # Chemins en UTF-8 : un nom d'utilisateur accentue est dans le dossier temporaire
    [Console]::InputEncoding = New-Object System.Text.UTF8Encoding $false
    Repondre "pret"
    while ($true) {
        $ligne = [Console]::In.ReadLine()
        if ([string]::IsNullOrEmpty($ligne)) { break }
        $parts = $ligne.Split("`t")
        if ($parts.Count -ge 2) { Lire $parts[0] $parts[1] }
        Repondre "fait"
    }
}
else {
    Lire $ImagePath $JsonPath
}
