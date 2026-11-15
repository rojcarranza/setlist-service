//go:build integration

// Package integration drives the real HTTP server end to end. The chat
// notifier is slow when SETLIST_NOTIFY_DELAY_MS says so; that is how the CI
// pipeline makes TestShareSetlist_NotifyTimeout fail on purpose.
package integration

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/rojcarranza/setlist-service/api"
	"github.com/rojcarranza/setlist-service/share"
	"github.com/rojcarranza/setlist-service/store"
)

func start(t *testing.T) *httptest.Server {
	t.Helper()
	srv := httptest.NewServer(api.Handler(store.New(), share.NotifierFromEnv(), "it", 500*time.Millisecond))
	t.Cleanup(srv.Close)
	return srv
}

func TestSetlistRoundTrip(t *testing.T) {
	srv := start(t)
	resp, err := http.Get(srv.URL + "/api/setlists/youth")
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	var sl struct{ Songs []struct{ Title string } }
	if err := json.NewDecoder(resp.Body).Decode(&sl); err != nil || len(sl.Songs) != 2 {
		t.Fatalf("err=%v songs=%d", err, len(sl.Songs))
	}
}

func TestTransposeEndpoint(t *testing.T) {
	srv := start(t)
	resp, err := http.Get(srv.URL + "/api/setlists/sunday?transpose=5")
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	var sl struct{ Songs []struct{ Key string } }
	if err := json.NewDecoder(resp.Body).Decode(&sl); err != nil {
		t.Fatal(err)
	}
	if sl.Songs[0].Key != "C" {
		t.Fatalf("G up 5 = %q, want C", sl.Songs[0].Key)
	}
}

func TestShareSetlist_NotifyTimeout(t *testing.T) {
	srv := start(t)
	resp, err := http.Post(srv.URL+"/api/setlists/sunday/share", "application/json", nil)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("share returned %d: the team was not notified in time", resp.StatusCode)
	}
}
