package main

import (
	"embed"
	"flag"
	"fmt"
	"io/fs"
	"net"
	"net/http"
	"os"
	"os/exec"
	"runtime"
	"time"
)

// Include underscore-prefixed Vite chunks as well as ordinary app assets.
//
//go:embed all:dist
var assets embed.FS

func main() {
	noBrowser := flag.Bool("no-browser", false, "do not open the browser automatically")
	installRoot := flag.String("install-update", "", "internal portable update helper")
	flag.Parse()
	if *installRoot != "" {
		if err := applyNativeUpdate(*installRoot); err != nil {
			fail(err)
		}
		return
	}
	const address = "127.0.0.1:5190"
	const url = "http://127.0.0.1:5190/"
	files, err := fs.Sub(assets, "dist")
	if err != nil {
		fail(err)
	}
	listener, err := net.Listen("tcp4", address)
	if err != nil {
		fail(fmt.Errorf("cannot start on %s: %w; close any other LaserForge launcher and try again", address, err))
	}
	fmt.Println("LaserForge Portable — offline local server")
	fmt.Println("Open", url, "in Chrome or Edge for USB machine control.")
	fmt.Println("Keep this window open. Press Ctrl+C to stop.")
	if !*noBrowser {
		var cmd *exec.Cmd
		switch runtime.GOOS {
		case "windows":
			cmd = exec.Command("rundll32", "url.dll,FileProtocolHandler", url)
		default:
			cmd = exec.Command("xdg-open", url)
		}
		if err := cmd.Start(); err != nil {
			fmt.Println("Open the address above manually:", err)
		} else {
			go cmd.Wait()
		}
	}
	mux := http.NewServeMux()
	mux.Handle("/", http.FileServer(http.FS(files)))
	if updater := portableUpdates(files); updater != nil {
		mux.HandleFunc("/api/portable-update", updater.handle)
	}
	server := &http.Server{Handler: mux, ReadHeaderTimeout: 5 * time.Second}
	if err := server.Serve(listener); err != nil {
		fail(err)
	}
}

func fail(err error) {
	fmt.Fprintln(os.Stderr, err)
	if runtime.GOOS == "windows" {
		fmt.Println("Press Enter to close.")
		fmt.Scanln()
	}
	os.Exit(1)
}
