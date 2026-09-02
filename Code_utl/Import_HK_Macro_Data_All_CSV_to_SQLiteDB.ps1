# =====================================================
# 脚本名称: HK_Macro_Data_Import_All_CSV_to_TADB.ps1
# 功能说明: 创建 SQLite3 数据库并导入所有 CSV 文件
# 特点: 
#   1. 使用数据字典定义表结构 (Config/hk_data_dictionary.json)
#   2. 如果表存在则自动删除并重建
#   3. 支持中文列名
#   4. 自动检测文件编码 (UTF-8-BOM / UTF-8 / GB2312)
#   5. 批量导入提升性能
#   6. 完整的日志记录功能
#   7. 自动将 CSV 中的 time_key 列名转换为 date
# 存放位置: TA_Workflow2/Code_utl
# 编码要求: 必须保存为 UTF-8-BOM 格式
# =====================================================

# ---------- 配置区域 ----------
# 获取脚本所在目录（兼容多种方式）
if ($PSScriptRoot) {
    $ScriptDir = $PSScriptRoot
} else {
    $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
}

if ([string]::IsNullOrEmpty($ScriptDir)) {
    $ScriptDir = (Get-Location).Path
    Write-Host "⚠️ 使用当前目录作为脚本目录: $ScriptDir" -ForegroundColor Yellow
}

$RootDir = Split-Path $ScriptDir -Parent

if ([string]::IsNullOrEmpty($RootDir)) {
    $RootDir = (Get-Item $ScriptDir).Parent.FullName
}

if ([string]::IsNullOrEmpty($RootDir) -or -not (Test-Path $RootDir)) {
    $currentDir = $ScriptDir
    for ($i = 0; $i -lt 5; $i++) {
        $parentDir = Split-Path $currentDir -Parent
        if ([string]::IsNullOrEmpty($parentDir)) {
            break
        }
        $currentDir = $parentDir
        if ((Test-Path (Join-Path $currentDir "Config")) -and (Test-Path (Join-Path $currentDir "Data"))) {
            $RootDir = $currentDir
            Write-Host "✅ 找到项目根目录: $RootDir" -ForegroundColor Green
            break
        }
    }
}

if ([string]::IsNullOrEmpty($RootDir) -or -not (Test-Path $RootDir)) {
    Write-Host "❌ 无法找到项目根目录，请确保脚本位于 Code_utl 目录下" -ForegroundColor Red
    exit 1
}

# 定义所有路径
$DataDir = Join-Path $RootDir "Data"
$DBDir = Join-Path $RootDir "SQLiteDB"
$DBPath = Join-Path $DBDir "HK_Stock.db"
$LogDir = Join-Path $RootDir "Log"
$LogFile = Join-Path $LogDir "HK_Macro_Data_Import_All_CSV_to_SQLiteDB.log"
$ConfigDir = Join-Path $RootDir "Config"
$DataDictFile = Join-Path $ConfigDir "hk_data_dictionary.json"

Write-Host ""
Write-Host "📋 路径配置:" -ForegroundColor Cyan
Write-Host "  数据字典: $DataDictFile" -ForegroundColor Gray
Write-Host "  数据库文件: $DBPath" -ForegroundColor Gray
Write-Host ""

# 设置控制台编码为 UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null

# 定义所有 CSV 文件及其对应的数据表名称
$CSVFiles = @(
    @{ File = "HK_IDX_HSI.csv"; Table = "hk_idx_hsi" },
    @{ File = "macro_data_hist.csv"; Table = "macro_data_hist" },
    @{ File = "SouthboundFlow_daily_hist.csv"; Table = "southbound_flow_hist" },
    @{ File = "HK_IDX_Hist.csv"; Table = "hk_idx_hist" },
    @{ File = "HK_IDX_VHSI.csv"; Table = "hk_idx_vhsi" },
    @{ File = "HK_IDX_HSBIO.csv"; Table = "hk_idx_hsbio" },
    @{ File = "HK_IDX_HSNU.csv"; Table = "hk_idx_hnu" },
    @{ File = "HK_IDX_HSNC.csv"; Table = "hk_idx_hnc" },
    @{ File = "HK_IDX_HSNP.csv"; Table = "hk_idx_hnp" },
    @{ File = "HK_IDX_HSNF.csv"; Table = "hk_idx_hnf" },
    @{ File = "HK_IDX_HSTECH.csv"; Table = "hk_idx_hstech" },
    @{ File = "HK_IDX_HSCEI.csv"; Table = "hk_idx_hscei" }
)

# ---------- 全局变量 ----------
$DataDictionary = $null

# ---------- 函数：创建目录 ----------
function Ensure-Directory {
    param([string]$Path, [bool]$Silent = $false)

    if ([string]::IsNullOrEmpty($Path)) {
        return $false
    }

    if (-not (Test-Path $Path)) {
        try {
            New-Item -ItemType Directory -Path $Path -Force | Out-Null
            if (-not $Silent) {
                Write-Host "  ✅ 已创建目录: $Path" -ForegroundColor Gray
            }
            return $true
        } catch {
            return $false
        }
    }
    return $true
}

# ---------- 日志函数 ----------
function Write-Log {
    param([string]$Message, [string]$Level = "INFO", [string]$ForegroundColor = "White")

    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $LogMessage = "[$Timestamp] [$Level] $Message"

    if (-not [string]::IsNullOrEmpty($LogDir)) {
        [void](Ensure-Directory -Path $LogDir -Silent $true)
    }

    if (-not [string]::IsNullOrEmpty($LogFile)) {
        try {
            [void](Add-Content -Path $LogFile -Value $LogMessage -Encoding UTF8 -ErrorAction SilentlyContinue)
        } catch {
            # 忽略
        }
    }

    if ($ForegroundColor -ne "White") {
        Write-Host $LogMessage -ForegroundColor $ForegroundColor
    } else {
        Write-Host $LogMessage
    }
}

# ---------- 函数：加载数据字典 ----------
function Load-DataDictionary {
    param([string]$FilePath)

    Write-Log -Message "尝试加载数据字典: $FilePath" -Level "INFO"

    if ([string]::IsNullOrEmpty($FilePath)) {
        Write-Log -Message "数据字典文件路径为空" -Level "ERROR" -ForegroundColor Red
        return $null
    }

    if (-not (Test-Path $FilePath)) {
        Write-Log -Message "数据字典文件不存在: $FilePath" -Level "ERROR" -ForegroundColor Red
        return $null
    }

    try {
        $jsonContent = Get-Content -Path $FilePath -Encoding UTF8 -Raw
        $dict = $jsonContent | ConvertFrom-Json

        Write-Log -Message "✅ 数据字典加载成功: $FilePath" -Level "INFO" -ForegroundColor Green
        Write-Log -Message "  版本: $($dict.version)" -Level "INFO"
        Write-Log -Message "  表数量: $($dict.tables.PSObject.Properties.Name.Count)" -Level "INFO"

        $tableNames = $dict.tables.PSObject.Properties.Name
        Write-Log -Message "  表列表: $($tableNames -join ', ')" -Level "INFO"

        return $dict
    } catch {
        Write-Log -Message "❌ 加载数据字典失败: $_" -Level "ERROR" -ForegroundColor Red
        return $null
    }
}

# ---------- 函数：从数据字典获取列类型 ----------
function Get-ColumnTypeFromDict {
    param([string]$TableName, [string]$ColumnName)

    if ($null -eq $DataDictionary) {
        return $null
    }

    try {
        $tableNameStr = [string]$TableName
        $columnNameStr = [string]$ColumnName

        $tableInfo = $DataDictionary.tables.$tableNameStr
        if ($null -eq $tableInfo) {
            return $null
        }

        $columnInfo = $tableInfo.columns.$columnNameStr
        if ($null -eq $columnInfo) {
            return $null
        }

        return $columnInfo.sqlite_type
    } catch {
        return $null
    }
}

# ---------- 函数：从数据字典获取表的所有列定义 ----------
function Get-TableColumnsFromDict {
    param([string]$TableName)

    if ($null -eq $DataDictionary) {
        return $null
    }

    try {
        $tableNameStr = [string]$TableName
        $tableInfo = $DataDictionary.tables.$tableNameStr
        if ($null -eq $tableInfo) {
            return $null
        }
        return $tableInfo.columns
    } catch {
        return $null
    }
}

# ---------- 函数：检查 CSV 文件 ----------
function Check-CSVFiles {
    $MissingFiles = @()
    foreach ($Item in $CSVFiles) {
        $FilePath = Join-Path $DataDir $Item.File
        if (-not (Test-Path $FilePath)) {
            $MissingFiles += $Item.File
        }
    }
    if ($MissingFiles.Count -gt 0) {
        $ErrorMessage = "以下 CSV 文件不存在: $($MissingFiles -join ', ')"
        Write-Log -Message $ErrorMessage -Level "ERROR" -ForegroundColor Red
        exit 1
    }
    Write-Host "✅ 所有 CSV 文件检查通过" -ForegroundColor Green
    Write-Log -Message "所有 CSV 文件检查通过" -Level "INFO" -ForegroundColor Green
}

# ---------- 函数：检测文件编码 ----------
function Get-FileEncoding {
    param([string]$FilePath)

    $bytes = [System.IO.File]::ReadAllBytes($FilePath)

    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
        return "UTF8-BOM"
    } elseif ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFF -and $bytes[1] -eq 0xFE) {
        return "UTF16-LE"
    } elseif ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFE -and $bytes[1] -eq 0xFF) {
        return "UTF16-BE"
    } else {
        try {
            $text = [System.IO.File]::ReadAllText($FilePath, [System.Text.Encoding]::UTF8)
            if ($text -match "�") {
                return "GB2312"
            }
            return "UTF8"
        } catch {
            return "GB2312"
        }
    }
}

# ---------- 函数：获取 CSV 列名（自动将 time_key 转换为 date） ----------
function Get-CSVHeaders {
    param([string]$FilePath, [string]$Encoding)

    $enc = $null
    switch ($Encoding) {
        "UTF8-BOM" { $enc = [System.Text.Encoding]::UTF8 }
        "GB2312"   { $enc = [System.Text.Encoding]::GetEncoding("GB2312") }
        "UTF8"     { $enc = [System.Text.Encoding]::UTF8 }
        default    { $enc = [System.Text.Encoding]::UTF8 }
    }

    $lines = [System.IO.File]::ReadAllLines($FilePath, $enc)
    if ($lines.Count -eq 0) {
        return $null
    }

    $headers = $lines[0].Split(',')
    $headers = $headers | ForEach-Object {
        $colName = [string]$_.Trim().Trim('"').Trim("'")
        # ★★★ 关键修改：将 time_key 转换为 date ★★★
        if ($colName -eq "time_key") {
            $colName = "date"
            Write-Log -Message "    列名转换: time_key → date" -Level "INFO" -ForegroundColor Yellow
        }
        return $colName
    }
    return $headers
}

# =====================================================
# ★★★ 修复：Generate-ColumnDefs 函数 ★★★
# =====================================================
function Generate-ColumnDefs {
    param(
        [string[]]$Headers,
        [string]$TableName
    )

    $colDefs = [System.Collections.ArrayList]::new()
    $tableNameStr = [string]$TableName

    # 尝试从数据字典获取列类型
    $dictColumns = Get-TableColumnsFromDict -TableName $tableNameStr

    foreach ($col in $Headers) {
        $colName = [string]$col
        $sqliteType = "TEXT"

        # 检查数据字典中是否有该列
        $dictColumnsExists = $false
        if ($null -ne $dictColumns) {
            foreach ($dictCol in $dictColumns.PSObject.Properties.Name) {
                if ($dictCol -eq $colName) {
                    $dictColumnsExists = $true
                    break
                }
            }
        }

        if ($dictColumnsExists) {
            $colInfo = $dictColumns.$colName
            $sqliteType = $colInfo.sqlite_type
            Write-Log -Message "    使用 数据字典 : $colName -> $sqliteType" -Level "INFO"
        } else {
            Write-Log -Message "    自动推断 : $colName -> $sqliteType" -Level "WARN"
        }

        # 生成列定义
        if ($colName -match '[^\x00-\x7F]' -or $colName -match '[^a-zA-Z0-9_]') {
            $def = "`"$colName`" $sqliteType"
        } else {
            $def = "$colName $sqliteType"
        }

        $colDefs.Add($def) | Out-Null
    }

    $result = $colDefs -join ", "

    Write-Log -Message "  生成的列定义: $result" -Level "INFO"

    return $result
}

# =====================================================
# ★★★ 修复：Generate-InsertSQL 函数 ★★★
# =====================================================
function Generate-InsertSQL {
    param(
        [string]$TableName,
        [string[]]$Headers,
        [string[]]$Values
    )

    $escapedValues = [System.Collections.ArrayList]::new()
    $tableNameStr = [string]$TableName

    for ($i = 0; $i -lt $Headers.Length; $i++) {
        $val = $Values[$i]
        $colName = [string]$Headers[$i]
        $cleanVal = [string]$val
        $cleanVal = $cleanVal.Trim('"').Trim("'").Trim()

        if ([string]::IsNullOrEmpty($cleanVal) -or $cleanVal -eq "NA" -or $cleanVal -eq "NaN") {
            $escapedValues.Add("NULL") | Out-Null
            continue
        }

        $colType = Get-ColumnTypeFromDict -TableName $tableNameStr -ColumnName $colName

        if ($colType) {
            $colTypeUpper = [string]$colType.ToUpper()
            switch ($colTypeUpper) {
                "INTEGER" {
                    $intVal = 0
                    if ([int]::TryParse($cleanVal, [ref]$intVal)) {
                        $escapedValues.Add($intVal.ToString()) | Out-Null
                    } else {
                        $escapedValues.Add("NULL") | Out-Null
                    }
                }
                "REAL" {
                    $floatVal = 0.0
                    if ([double]::TryParse($cleanVal, [System.Globalization.NumberStyles]::Any,
                                          [System.Globalization.CultureInfo]::InvariantCulture,
                                          [ref]$floatVal)) {
                        $escapedValues.Add($floatVal.ToString()) | Out-Null
                    } else {
                        $escapedValues.Add("NULL") | Out-Null
                    }
                }
                default {
                    $escaped = $cleanVal -replace "'", "''"
                    $escapedValues.Add("'$escaped'") | Out-Null
                }
            }
        } else {
            if ($cleanVal -match '^-?\d+\.?\d*$' -or $cleanVal -match '^-?\d+\.?\d*[eE][+-]?\d+$') {
                $escapedValues.Add($cleanVal) | Out-Null
            } else {
                $escaped = $cleanVal -replace "'", "''"
                $escapedValues.Add("'$escaped'") | Out-Null
            }
        }
    }

    # 构建列名列表
    $cols = [System.Collections.ArrayList]::new()
    foreach ($col in $Headers) {
        $colName = [string]$col
        if ($colName -match '[^\x00-\x7F]' -or $colName -match '[^a-zA-Z0-9_]') {
            $cols.Add("`"$colName`"") | Out-Null
        } else {
            $cols.Add($colName) | Out-Null
        }
    }

    $colsStr = $cols -join ", "
    $valuesStr = $escapedValues -join ", "

    return "INSERT INTO $tableNameStr ($colsStr) VALUES ($valuesStr);"
}

# =====================================================
# ★★★ 修复：Drop-Table-If-Exists 函数 ★★★
# =====================================================
function Drop-Table-If-Exists {
    param([string]$TableName)

    $tableNameStr = [string]$TableName
    $checkSQL = "SELECT name FROM sqlite_master WHERE type='table' AND name='$tableNameStr';"

    $result = sqlite3 $DBPath $checkSQL 2>$null

    $resultStr = ""
    if ($null -ne $result) {
        $resultStr = ($result -join "").Trim()
    }

    if ($resultStr -eq $tableNameStr) {
        sqlite3 $DBPath "DROP TABLE IF EXISTS $tableNameStr;" 2>$null | Out-Null
        Write-Host "  ✅ 已删除旧表: $tableNameStr" -ForegroundColor Yellow
        Write-Log -Message "已删除旧表: $tableNameStr" -Level "INFO"
        return $true
    } else {
        Write-Host "  表不存在，无需删除: $tableNameStr" -ForegroundColor Gray
        Write-Log -Message "表不存在，无需删除: $tableNameStr" -Level "INFO"
        return $false
    }
}

# ---------- 函数：导入 CSV ----------
function Import-CSV-With-Chinese {
    param([string]$CSVPath, [string]$TableName)

    $tableNameStr = [string]$TableName

    Write-Host "  正在导入: $tableNameStr ..." -ForegroundColor Gray
    Write-Log -Message "开始导入表: $tableNameStr, 文件: $(Split-Path $CSVPath -Leaf)" -Level "INFO"

    $StartTime = Get-Date

    $encoding = Get-FileEncoding -FilePath $CSVPath
    Write-Host "    文件编码: $encoding" -ForegroundColor Gray
    Write-Log -Message "  文件编码: $encoding" -Level "INFO"

    # ★★★ 获取列名（自动将 time_key 转换为 date） ★★★
    $headers = Get-CSVHeaders -FilePath $CSVPath -Encoding $encoding
    if ($null -eq $headers -or $headers.Count -eq 0) {
        Write-Host "  ❌ $tableNameStr 导入失败: 无法读取列名" -ForegroundColor Red
        Write-Log -Message "导入失败 $tableNameStr : 无法读取列名" -Level "ERROR"
        return $false
    }
    Write-Host "    列名: $($headers -join ', ')" -ForegroundColor Gray
    Write-Log -Message "  列名: $($headers -join ', ')" -Level "INFO"

    Drop-Table-If-Exists -TableName $tableNameStr

    # 创建新表
    $colDefs = Generate-ColumnDefs -Headers $headers -TableName $tableNameStr
    $createSQL = "CREATE TABLE $tableNameStr ($colDefs);"
    Write-Host "    创建表 SQL: $createSQL" -ForegroundColor Gray
    Write-Log -Message "  创建表: $createSQL" -Level "INFO"

    try {
        sqlite3 $DBPath $createSQL 2>$null | Out-Null
        Write-Host "    表结构已创建" -ForegroundColor Gray
        Write-Log -Message "  表结构已创建" -Level "INFO"
    } catch {
        Write-Host "  ❌ $tableNameStr 创建表失败: $_" -ForegroundColor Red
        Write-Log -Message "导入失败 $tableNameStr : 创建表失败" -Level "ERROR"
        return $false
    }

    # 读取 CSV 数据
    $enc = $null
    switch ($encoding) {
        "UTF8-BOM" { $enc = [System.Text.Encoding]::UTF8 }
        "GB2312"   { $enc = [System.Text.Encoding]::GetEncoding("GB2312") }
        "UTF8"     { $enc = [System.Text.Encoding]::UTF8 }
        default    { $enc = [System.Text.Encoding]::UTF8 }
    }

    $lines = [System.IO.File]::ReadAllLines($CSVPath, $enc)
    if ($lines.Count -le 1) {
        Write-Host "  ❌ $tableNameStr 导入失败: CSV 文件为空" -ForegroundColor Red
        Write-Log -Message "导入失败 $tableNameStr : CSV 文件为空" -Level "ERROR"
        return $false
    }

    $dataLines = $lines[1..($lines.Count - 1)]
    $rowCount = 0
    $batchSize = 100
    $batchSQL = ""

    foreach ($line in $dataLines) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }

        # 解析 CSV 行（支持引号）
        $values = @()
        $current = ""
        $inQuotes = $false
        for ($i = 0; $i -lt $line.Length; $i++) {
            $char = $line[$i]
            if ($char -eq '"' -or $char -eq "'") {
                if ($inQuotes -and $i + 1 -lt $line.Length -and $line[$i+1] -eq $char) {
                    $current += $char
                    $i++
                } else {
                    $inQuotes = -not $inQuotes
                }
            } elseif ($char -eq ',' -and -not $inQuotes) {
                $values += $current
                $current = ""
            } else {
                $current += $char
            }
        }
        $values += $current

        # 确保列数匹配
        if ($values.Count -lt $headers.Count) {
            while ($values.Count -lt $headers.Count) {
                $values += ""
            }
        } elseif ($values.Count -gt $headers.Count) {
            $values = $values[0..($headers.Count - 1)]
        }

        $insertSQL = Generate-InsertSQL -TableName $tableNameStr -Headers $headers -Values $values
        $batchSQL += $insertSQL
        $rowCount++

        if ($rowCount % $batchSize -eq 0) {
            sqlite3 $DBPath $batchSQL 2>$null | Out-Null
            $batchSQL = ""
            Write-Host "    已导入 $rowCount 行..." -ForegroundColor Gray
        }
    }

    if ($batchSQL -ne "") {
        sqlite3 $DBPath $batchSQL 2>$null | Out-Null
    }

    # 验证行数
    $countResult = sqlite3 $DBPath "SELECT COUNT(*) FROM $tableNameStr;" 2>$null
    if ($null -ne $countResult) {
        $count = ($countResult -join "").Trim()
    } else {
        $count = "Error"
    }

    $EndTime = Get-Date
    $Duration = $EndTime - $StartTime

    Write-Host "  ✅ $tableNameStr 导入成功，共 $rowCount 行 (耗时: $($Duration.TotalSeconds.ToString('F2'))秒)" -ForegroundColor Green
    Write-Log -Message "导入成功 $tableNameStr : $rowCount 行, 耗时: $($Duration.TotalSeconds.ToString('F2'))秒" -Level "INFO" -ForegroundColor Green
    return $true
}

# ---------- 函数：显示统计 ----------
function Show-Statistics {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "导入完成！数据统计如下:" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan

    Write-Log -Message "========== 数据统计 ==========" -Level "INFO"

    foreach ($Item in $CSVFiles) {
        $tableNameStr = [string]$Item.Table
        $countResult = sqlite3 $DBPath "SELECT COUNT(*) FROM $tableNameStr;" 2>$null

        if ($null -eq $countResult) {
            Write-Host "  $tableNameStr : 查询失败" -ForegroundColor Yellow
            Write-Log -Message "  $tableNameStr : 查询失败" -Level "WARN"
        } else {
            $Count = ($countResult -join "").Trim()
            if ($Count -match '^[0-9]+$') {
                Write-Host "  $tableNameStr : $Count 行" -ForegroundColor White
                Write-Log -Message "  $tableNameStr : $Count 行" -Level "INFO"
            } else {
                Write-Host "  $tableNameStr : 空表或导入失败" -ForegroundColor Yellow
                Write-Log -Message "  $tableNameStr : 空表或导入失败" -Level "WARN"
            }
        }
    }
}

# =====================================================
# 主程序开始
# =====================================================
Clear-Host

$ScriptStartTime = Get-Date

[void](Ensure-Directory -Path $LogDir -Silent $false)
[void](Ensure-Directory -Path $DBDir -Silent $false)
[void](Ensure-Directory -Path $DataDir -Silent $false)

Write-Log -Message "========================================" -Level "INFO"
Write-Log -Message "  创建 SQLite3 数据库并导入所有 CSV 文件" -Level "INFO"
Write-Log -Message "  使用数据字典定义表结构 | 自动删除并重建表" -Level "INFO"
Write-Log -Message "  自动将 time_key 列名转换为 date" -Level "INFO"
Write-Log -Message "========================================" -Level "INFO"
Write-Log -Message "脚本目录: $ScriptDir" -Level "INFO"
Write-Log -Message "项目根目录: $RootDir" -Level "INFO"
Write-Log -Message "数据字典: $DataDictFile" -Level "INFO"
Write-Log -Message "数据库路径: $DBPath" -Level "INFO"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  创建 SQLite3 数据库并导入所有 CSV 文件" -ForegroundColor Cyan
Write-Host "  使用数据字典定义表结构 | 自动删除并重建表" -ForegroundColor Cyan
Write-Host "  自动将 time_key 列名转换为 date" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "脚本目录: $ScriptDir" -ForegroundColor Gray
Write-Host "项目根目录: $RootDir" -ForegroundColor Gray
Write-Host "数据字典: $DataDictFile" -ForegroundColor Gray
Write-Host "数据库路径: $DBPath" -ForegroundColor Gray
Write-Host ""

# 加载数据字典
Write-Host "[1/4] 加载数据字典..." -ForegroundColor Yellow
Write-Log -Message "[1/4] 加载数据字典..." -Level "INFO"

if (-not (Test-Path $ConfigDir)) {
    Write-Host "  ⚠️ Config 目录不存在: $ConfigDir" -ForegroundColor Yellow
    Write-Log -Message "Config 目录不存在" -Level "WARN"
    [void](Ensure-Directory -Path $ConfigDir -Silent $false)
}

$DataDictionary = Load-DataDictionary -FilePath $DataDictFile

if ($DataDictionary -ne $null) {
    Write-Host "  ✅ 数据字典加载成功" -ForegroundColor Green
} else {
    Write-Host "  ⚠️ 数据字典加载失败，将使用自动推断" -ForegroundColor Yellow
}

# 检查 CSV 文件
Write-Host ""
Write-Host "[2/4] 检查 CSV 文件..." -ForegroundColor Yellow
Write-Log -Message "[2/4] 检查 CSV 文件..." -Level "INFO"
Check-CSVFiles

# 导入 CSV 文件
Write-Host ""
Write-Host "[3/4] 开始导入 CSV 文件..." -ForegroundColor Yellow
Write-Log -Message "[3/4] 开始导入 CSV 文件..." -Level "INFO"
$SuccessCount = 0
$FailCount = 0

foreach ($Item in $CSVFiles) {
    $CSVPath = Join-Path $DataDir $Item.File
    if (Import-CSV-With-Chinese -CSVPath $CSVPath -TableName $Item.Table) {
        $SuccessCount++
    } else {
        $FailCount++
    }
}

# 显示统计
Show-Statistics

# 计算总耗时
$ScriptEndTime = Get-Date
$TotalDuration = $ScriptEndTime - $ScriptStartTime

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "导入汇总: 成功 $SuccessCount 个, 失败 $FailCount 个" -ForegroundColor Cyan
Write-Host "总耗时: $($TotalDuration.TotalMinutes.ToString('F2')) 分钟" -ForegroundColor Cyan
Write-Host "数据库文件: $DBPath" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan

Write-Log -Message "========================================" -Level "INFO"
Write-Log -Message "导入汇总: 成功 $SuccessCount 个, 失败 $FailCount 个" -Level "INFO"
Write-Log -Message "总耗时: $($TotalDuration.TotalMinutes.ToString('F2')) 分钟" -Level "INFO"
Write-Log -Message "数据库文件: $DBPath" -Level "INFO"
Write-Log -Message "========================================" -Level "INFO"

Write-Host ""
Write-Host "按任意键退出..." -ForegroundColor Gray
Read-Host
