package main

import (
	"fmt"
	"github.com/datumbrain/label-printer/tag"
	"image"
	"image/png"
	"os"
	"time"
)

func PrintTag(text, qrText string) error {
	tg := tag.NewGenerator(96, 320)

	img, err := tg.GenerateImage(text, qrText)
	if err != nil {
		return err
	}

	filename := fmt.Sprintf("images/%d.png", time.Now().UnixMicro())

	err = saveImageToPng(filename, img)
	if err != nil {
		return err
	}

	mac := os.Getenv("PRINTER_MAC")
	err = runPythonScript("./niimprint/niimprint/__main__.py", "-a", mac, filename)
	if err != nil {
		return err
	}

	return nil
}

func saveImageToPng(filename string, img image.Image) error {
	f, err := os.OpenFile(filename, os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return err
	}
	defer f.Close()

	return png.Encode(f, img)
}
