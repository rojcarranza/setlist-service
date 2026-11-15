package api

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/rojcarranza/setlist-service/share"
	"github.com/rojcarranza/setlist-service/store"
)

func server() http.Handler {
	return Handler(store.New(), share.DelayNotifier{Delay: time.Millisecond}, "1.2.3", time.Second)
}

func get(t *testing.T, path string) *httptest.ResponseRecorder {
	t.Helper()
	rec := httptest.NewRecorder()
	server().ServeHTTP(rec, httptest.NewRequest("GET", path, nil))
	return rec
}

func TestHealthReportsVersion(t *testing.T) {
	rec := get(t, "/health")
	if rec.Code != 200 || !strings.Contains(rec.Body.String(), `"version":"1.2.3"`) {
		t.Fatalf("%d %s", rec.Code, rec.Body)
	}
}

func TestListSetlists(t *testing.T) {
	rec := get(t, "/api/setlists")
	var got []map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil || len(got) != 2 {
		t.Fatalf("err=%v body=%s", err, rec.Body)
	}
}

func TestGetMissingSetlist(t *testing.T) {
	if code := get(t, "/api/setlists/nope").Code; code != 404 {
		t.Fatalf("code = %d", code)
	}
}

func TestTransposeQuery(t *testing.T) {
	rec := get(t, "/api/setlists/sunday?transpose=2")
	if !strings.Contains(rec.Body.String(), `"key":"A"`) {
		t.Fatalf("G up 2 should be A: %s", rec.Body)
	}
}

func TestTransposeQueryRejectsNonNumber(t *testing.T) {
	if code := get(t, "/api/setlists/sunday?transpose=up").Code; code != 400 {
		t.Fatalf("code = %d", code)
	}
}

func TestShare(t *testing.T) {
	rec := httptest.NewRecorder()
	server().ServeHTTP(rec, httptest.NewRequest("POST", "/api/setlists/sunday/share", nil))
	if rec.Code != 200 || !strings.Contains(rec.Body.String(), `"link":"/s/`) {
		t.Fatalf("%d %s", rec.Code, rec.Body)
	}
}
