# setlist-service

A small Go web service for worship teams: songs, keys and setlists. It is the
sample application that forge-lab's `SETLIST-*` Bamboo plans build, test,
package and deploy, so the Bamboo CLI (bam) has real pipelines to demonstrate
against.

```
GET  /health                       status and version
GET  /api/setlists                 every setlist, by date
GET  /api/setlists/{id}            one setlist; ?transpose=N moves every key N semitones
POST /api/setlists/{id}/share      share link; tells the team, times out after 2s
```

```
go test ./...                              # unit tests
go test -tags integration ./integration/   # end to end; SETLIST_NOTIFY_DELAY_MS slows the chat notifier
go run ./cmd/setlist                       # :8080, SETLIST_ADDR to change
```

Packages: `song`, `setlist`, `transpose`, `share`, `store` (in memory), `api`.
