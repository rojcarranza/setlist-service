// Command setlist serves the setlist API.
package main

import (
	"log"
	"net/http"
	"os"
	"time"

	"github.com/rojcarranza/setlist-service/api"
	"github.com/rojcarranza/setlist-service/share"
	"github.com/rojcarranza/setlist-service/store"
)

// version is set at build time: -ldflags "-X main.version=1.4.0".
var version = "dev"

func main() {
	addr := ":8080"
	if v := os.Getenv("SETLIST_ADDR"); v != "" {
		addr = v
	}
	h := api.Handler(store.New(), share.NotifierFromEnv(), version, 2*time.Second)
	log.Printf("setlist %s listening on %s", version, addr)
	log.Fatal(http.ListenAndServe(addr, h))
}
