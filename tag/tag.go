package tag

import (
	"github.com/datumbrain/label-printer/qr"
	"github.com/datumbrain/label-printer/text"
	"golang.org/x/image/draw"
	"image"
	"image/color"
	"strings"
)

type Generator struct {
	height int
	width  int
}

func NewGenerator(height, width int) *Generator {
	return &Generator{height: height, width: width}
}

func (g Generator) GenerateImage(tag, qrText string) (image.Image, error) {
	qrSize := g.height
	qrCode, err := qr.GetImage(qrText, qrSize)
	if err != nil {
		return nil, err
	}

	fontSize := 20.0
	spacing := 1.15
	lineHeight := int(fontSize * spacing)
	lines := 1 + strings.Count(tag, "\n")
	txtHeight := lineHeight*lines + int(fontSize/4)
	txtWidth := g.width - qrSize

	txt, err := text.GetImage(text.Config{
		Height:      txtHeight,
		Width:       txtWidth,
		DPI:         72.0,
		Padding:     14,
		FontFile:    "fonts/NanumGothicBold.ttf",
		FontSize:    fontSize,
		Hinting:     text.Full,
		Spacing:     spacing,
		WhiteOnBlack: false,
	}, tag)
	if err != nil {
		return nil, err
	}

	output := image.NewRGBA(image.Rect(0, 0, g.width, g.height))
	draw.Draw(output, output.Bounds(), &image.Uniform{C: color.White}, image.Point{}, draw.Src)

	// 텍스트 왼쪽, 세로 중앙
	txtY := (g.height - txtHeight) / 2
	draw.Draw(output,
		image.Rect(0, txtY, txtWidth, txtY+txt.Bounds().Dy()),
		txt, image.Point{}, draw.Over)

	// QR 오른쪽 크게
	draw.Draw(output,
		image.Rect(txtWidth, 0, g.width, g.height),
		qrCode, image.Point{}, draw.Over)

	return output, nil
}
