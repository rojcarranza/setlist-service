// Package share publishes a setlist to the team and tells them about it.
package share

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"os"
	"strconv"
	"time"

	"github.com/rojcarranza/setlist-service/setlist"
)

// Notifier tells the team a setlist was shared.
type Notifier interface {
	Notify(ctx context.Context, link string) error
}

// Link is the stable share link for a setlist.
func Link(sl setlist.Setlist) string {
	sum := sha256.Sum256([]byte(sl.ID + sl.Name + sl.Date))
	return "/s/" + hex.EncodeToString(sum[:])[:10]
}

// Setlist shares sl and waits at most timeout for the team to be notified.
func Setlist(ctx context.Context, sl setlist.Setlist, n Notifier, timeout time.Duration) (string, error) {
	ctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	link := Link(sl)
	if err := n.Notify(ctx, link); err != nil {
		return "", fmt.Errorf("notify team: %w", err)
	}
	return link, nil
}

// DelayNotifier stands in for the chat service: it answers after Delay.
type DelayNotifier struct{ Delay time.Duration }

// Notify waits Delay, or gives up when ctx ends first.
func (d DelayNotifier) Notify(ctx context.Context, _ string) error {
	select {
	case <-time.After(d.Delay):
		return nil
	case <-ctx.Done():
		return ctx.Err()
	}
}

// NotifierFromEnv reads SETLIST_NOTIFY_DELAY_MS, the chat service's pretend
// latency; unset means 20 ms.
func NotifierFromEnv() DelayNotifier {
	ms := 20
	if v, err := strconv.Atoi(os.Getenv("SETLIST_NOTIFY_DELAY_MS")); err == nil {
		ms = v
	}
	return DelayNotifier{Delay: time.Duration(ms) * time.Millisecond}
}
