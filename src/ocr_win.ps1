# ocr_win.ps1 — OCR via le moteur integre a Windows (Windows.Media.Ocr).
#
# Aucune dependance externe, aucun binaire a embarquer, aucun acces reseau :
# le moteur fait partie de Windows 10/11 et tourne hors ligne.
#
# Appele par sante.py (captures FitDays) et vocabulaire.py (listes de mots) :
#   powershell -NoProfile -ExecutionPolicy Bypass -File ocr_win.ps1
#              -ImagePath <png> -JsonPath <json>
#
# Ecrit un JSON UTF-8 (sans BOM) :
#   {ok, lang, width, height, angle, words:[{t,l,x,y,w,h}]}
# Les positions sont indispensables : c'est elles qui permettent d'apparier
# un libelle a sa valeur sur la meme ligne, l'ordre de lecture du moteur
# n'etant pas fiable sur une mise en page en colonnes.
#
# Mode PDF (vocabulaire.py) : avec -PdfDir, ImagePath est un PDF dont chaque
# page est rendue en PNG dans ce dossier par le moteur PDF de Windows
# (Windows.Data.Pdf, hors ligne lui aussi), SANS lecture. Le JSON vaut alors
#   {ok, total, pages:[chemins des PNG]}
# et chaque page repasse ensuite par ce script comme une image.

param(
    [Parameter(Mandatory = $true)][string]$ImagePath,
    [Parameter(Mandatory = $true)][string]$JsonPath,
    [string]$PdfDir = "",
    [int]$PdfMaxPages = 20
)

$ErrorActionPreference = "Stop"

function Write-Json($obj) {
    $json = $obj | ConvertTo-Json -Depth 4 -Compress
    [System.IO.File]::WriteAllText($JsonPath, $json, (New-Object System.Text.UTF8Encoding $false))
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

    if ($PdfDir) {
        # Meme passerelle, pour une operation qui ne renvoie rien (IAsyncAction)
        $asTaskAction = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
            $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
            $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncAction' })[0]
        [Windows.Data.Pdf.PdfDocument, Windows.Data.Pdf, ContentType = WindowsRuntime] | Out-Null

        $file   = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($ImagePath)) ([Windows.Storage.StorageFile])
        $doc    = Await ([Windows.Data.Pdf.PdfDocument]::LoadFromFileAsync($file)) ([Windows.Data.Pdf.PdfDocument])
        $folder = Await ([Windows.Storage.StorageFolder]::GetFolderFromPathAsync($PdfDir)) ([Windows.Storage.StorageFolder])
        $n = [Math]::Min([int]$doc.PageCount, $PdfMaxPages)
        $pages = for ($i = 0; $i -lt $n; $i++) {
            $page = $doc.GetPage($i)
            # Deux fois la taille nominale (~190 dpi) : le texte courant fait
            # alors une vingtaine de pixels de haut, ce que le moteur lit le
            # mieux. Plafond de 4000 px pour une page geante.
            $f = [Math]::Min(2.0, 4000 / [Math]::Max($page.Size.Width, $page.Size.Height))
            $opt = New-Object Windows.Data.Pdf.PdfPageRenderOptions
            $opt.DestinationWidth  = [uint32][Math]::Round($page.Size.Width * $f)
            $opt.DestinationHeight = [uint32][Math]::Round($page.Size.Height * $f)
            $png    = Await ($folder.CreateFileAsync("page$($i + 1).png", [Windows.Storage.CreationCollisionOption]::ReplaceExisting)) ([Windows.Storage.StorageFile])
            $stream = Await ($png.OpenAsync([Windows.Storage.FileAccessMode]::ReadWrite)) ([Windows.Storage.Streams.IRandomAccessStream])
            $asTaskAction.Invoke($null, @($page.RenderToStreamAsync($stream, $opt))).Wait(-1) | Out-Null
            $stream.Dispose()
            $page.Dispose()
            $png.Path
        }
        Write-Json ([pscustomobject]@{ ok = $true; total = [int]$doc.PageCount; pages = @($pages) })
        exit 0
    }

    [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime] | Out-Null
    [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null

    $file    = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($ImagePath)) ([Windows.Storage.StorageFile])
    $stream  = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
    $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bitmap  = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])

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
    if ($null -eq $engine) {
        Write-Json ([pscustomobject]@{ ok = $false; error = "no_engine" })
        exit 0
    }

    $result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])

    # `l` : numero de la ligne du moteur. Il separe deja deux colonnes de texte
    # et suit l'inclinaison d'une photo : vocabulaire.py regroupe par ligne.
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
    })
}
catch {
    Write-Json ([pscustomobject]@{ ok = $false; error = $_.Exception.Message })
}
