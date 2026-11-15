// Package api is the HTTP face of the setlist service.
package api

import (
	"encoding/json"
	"net/http"
	"strconv"
	"time"

	"github.com/rojcarranza/setlist-service/share"
	"github.com/rojcarranza/setlist-service/store"
)

// Handler serves the setlist API. Version is what /health reports.
func Handler(st *store.Store, n share.Notifier, version string, notifyTimeout time.Duration) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{"status": "ok", "version": version})
	})
	mux.HandleFunc("GET /api/setlists", func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, http.StatusOK, st.List())
	})
	mux.HandleFunc("GET /api/setlists/{id}", func(w http.ResponseWriter, r *http.Request) {
		sl, ok := st.Get(r.PathValue("id"))
		if !ok {
			http.Error(w, "no such setlist", http.StatusNotFound)
			return
		}
		if by := r.URL.Query().Get("transpose"); by != "" {
			n, err := strconv.Atoi(by)
			if err != nil {
				http.Error(w, "transpose must be a number of semitones", http.StatusBadRequest)
				return
			}
			if sl, err = sl.Transposed(n); err != nil {
				http.Error(w, err.Error(), http.StatusUnprocessableEntity)
				return
			}
		}
		writeJSON(w, http.StatusOK, sl)
	})
	mux.HandleFunc("POST /api/setlists/{id}/share", func(w http.ResponseWriter, r *http.Request) {
		sl, ok := st.Get(r.PathValue("id"))
		if !ok {
			http.Error(w, "no such setlist", http.StatusNotFound)
			return
		}
		link, err := share.Setlist(r.Context(), sl, n, notifyTimeout)
		if err != nil {
			http.Error(w, err.Error(), http.StatusGatewayTimeout)
			return
		}
		writeJSON(w, http.StatusOK, map[string]string{"link": link})
	})
	return mux
}

func writeJSON(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(v)
}
