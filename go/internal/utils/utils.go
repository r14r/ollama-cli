package utils

import (
	"fmt"
	"os"
	"strconv"
	"strings"
)

func FormatSize(bytes int64, unit string) string {
	if unit == "gb" {
		return fmt.Sprintf("%.2f GB", float64(bytes)/(1024*1024*1024))
	}
	return fmt.Sprintf("%.2f MB", float64(bytes)/(1024*1024))
}

func SupportsColor() bool {
	return os.Getenv("NO_COLOR") == ""
}

func Colorize(text string, color string, enable bool) string {
	if !enable {
		return text
	}
	return fmt.Sprintf("\033[%sm%s\033[0m", color, text)
}

func ParseSizeToBytes(sizeStr string) int64 {
	parts := strings.Fields(strings.TrimSpace(sizeStr))
	if len(parts) < 2 {
		return 0
	}
	val, err := strconv.ParseFloat(parts[0], 64)
	if err != nil {
		return 0
	}
	unit := strings.ToLower(parts[1])
	switch {
	case strings.Contains(unit, "gb"):
		return int64(val * 1024 * 1024 * 1024)
	case strings.Contains(unit, "mb"):
		return int64(val * 1024 * 1024)
	case strings.Contains(unit, "kb"):
		return int64(val * 1024)
	default:
		return int64(val)
	}
}

func ParseRelativeTimeToSeconds(timeStr string) int64 {
	s := strings.ToLower(strings.TrimSpace(timeStr))
	s = strings.ReplaceAll(s, "ago", "")
	parts := strings.Fields(s)
	if len(parts) < 2 {
		return 0
	}
	val, err := strconv.ParseFloat(parts[0], 64)
	if err != nil {
		return 9999999999
	}
	unit := parts[1]
	var factor int64 = 1
	switch {
	case strings.Contains(unit, "second"):
		factor = 1
	case strings.Contains(unit, "minute"):
		factor = 60
	case strings.Contains(unit, "hour"):
		factor = 3600
	case strings.Contains(unit, "day"):
		factor = 86400
	case strings.Contains(unit, "week"):
		factor = 86400 * 7
	case strings.Contains(unit, "month"):
		factor = 86400 * 30
	case strings.Contains(unit, "year"):
		factor = 86400 * 365
	}
	return int64(val * float64(factor))
}

func PrintTable(rows []map[string]string, columns []string, enableColor bool) {
	if len(rows) == 0 {
		fmt.Println("No rows.")
		return
	}

	widths := make(map[string]int)
	for _, col := range columns {
		widths[col] = len(col)
		for _, row := range rows {
			if len(row[col]) > widths[col] {
				widths[col] = len(row[col])
			}
		}
	}

	header := ""
	for i, col := range columns {
		if i > 0 {
			header += "  "
		}
		header += padRight(col, widths[col])
	}
	fmt.Println(Colorize(header, "1;37", enableColor))
	fmt.Println(strings.Repeat("-", len(header)))

	for _, r := range rows {
		isOrphan := r["is_orphan"] == "yes"
		line := ""
		for i, col := range columns {
			if i > 0 {
				line += "  "
			}
			val := padRight(r[col], widths[col])
			if isOrphan {
				val = Colorize(val, "31", enableColor)
			}
			line += val
		}
		fmt.Println(line)
	}
}

func padRight(s string, width int) string {
	if len(s) >= width {
		return s
	}
	return s + strings.Repeat(" ", width-len(s))
}
