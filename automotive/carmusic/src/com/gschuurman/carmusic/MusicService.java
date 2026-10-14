package com.gschuurman.carmusic;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.ServiceInfo;
import android.os.Bundle;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.Looper;
import android.support.v4.media.MediaBrowserCompat.MediaItem;
import android.support.v4.media.MediaDescriptionCompat;
import android.support.v4.media.session.MediaSessionCompat;
import android.support.v4.media.session.PlaybackStateCompat;
import android.text.TextUtils;

import androidx.core.app.NotificationCompat;
import androidx.media.MediaBrowserServiceCompat;
import androidx.media.app.NotificationCompat.MediaStyle;

import java.util.ArrayList;
import java.util.List;

/**
 * The car media source: browse tree and search from MusicLibrary, playback through Playback. The
 * queue and position are saved, so the last song is ready to resume after a reboot.
 */
public final class MusicService extends MediaBrowserServiceCompat implements Playback.Listener {
    private static final String CHANNEL = "playback";
    private static final int NOTIFICATION_ID = 1;
    private static final String PREFS = "playback";
    private static final String KEY_QUEUE = "queue", KEY_INDEX = "index", KEY_POSITION = "position",
            KEY_SHUFFLE = "shuffle", KEY_REPEAT = "repeat";
    /** Larger queues are trimmed around the current song (binder transaction size). */
    private static final int MAX_QUEUE = 500;
    private static final long ACTIONS = PlaybackStateCompat.ACTION_PLAY
            | PlaybackStateCompat.ACTION_PAUSE | PlaybackStateCompat.ACTION_PLAY_PAUSE
            | PlaybackStateCompat.ACTION_STOP | PlaybackStateCompat.ACTION_SEEK_TO
            | PlaybackStateCompat.ACTION_SKIP_TO_NEXT | PlaybackStateCompat.ACTION_SKIP_TO_PREVIOUS
            | PlaybackStateCompat.ACTION_SKIP_TO_QUEUE_ITEM
            | PlaybackStateCompat.ACTION_PLAY_FROM_MEDIA_ID
            | PlaybackStateCompat.ACTION_PLAY_FROM_SEARCH
            | PlaybackStateCompat.ACTION_SET_SHUFFLE_MODE
            | PlaybackStateCompat.ACTION_SET_REPEAT_MODE;

    // Custom actions in Now Playing (shown in this order).
    private static final String ACTION_SHUFFLE = "shuffle";
    private static final String ACTION_REPEAT = "repeat";
    private static final String ACTION_FAVORITE = "favorite";

    private MusicLibrary mLibrary;
    private PlaylistStore mStore;
    private Playback mPlayback;
    private MediaSessionCompat mSession;
    private Handler mWorker;
    private final Handler mMain = new Handler(Looper.getMainLooper());
    private boolean mForeground;

    @Override
    public void onCreate() {
        super.onCreate();
        mStore = new PlaylistStore(this);
        mLibrary = new MusicLibrary(this, mStore);
        mPlayback = new Playback(this, this);
        final HandlerThread thread = new HandlerThread("CarMusicLibrary");
        thread.start();
        mWorker = new Handler(thread.getLooper());

        mSession = new MediaSessionCompat(this, "CarMusic");
        mSession.setCallback(new SessionCallback());
        mSession.setSessionActivity(PendingIntent.getActivity(this, 0,
                new Intent(this, ImportActivity.class), PendingIntent.FLAG_IMMUTABLE));
        setSessionToken(mSession.getSessionToken());
        getSystemService(NotificationManager.class).createNotificationChannel(new NotificationChannel(
                CHANNEL, getString(R.string.channel_playback), NotificationManager.IMPORTANCE_LOW));
        updateState();
        restore();
        CoverFetchJob.schedule(this, false);
    }

    @Override
    public void onDestroy() {
        save();
        mPlayback.stop();
        mSession.release();
        mWorker.getLooper().quitSafely();
        super.onDestroy();
    }

    @Override
    public BrowserRoot onGetRoot(String clientPackageName, int clientUid, Bundle rootHints) {
        final Bundle extras = new Bundle();
        extras.putBoolean("android.media.browse.SEARCH_SUPPORTED", true);
        return new BrowserRoot(MusicLibrary.ROOT, extras);
    }

    @Override
    public void onLoadChildren(String parentId, Result<List<MediaItem>> result) {
        result.detach();
        mWorker.post(() -> result.sendResult(mLibrary.children(parentId)));
    }

    @Override
    public void onSearch(String query, Bundle extras, Result<List<MediaItem>> result) {
        result.detach();
        mWorker.post(() -> {
            final List<MediaItem> items = new ArrayList<>();
            for (MusicLibrary.Song s : mLibrary.search(query)) {
                items.add(new MediaItem(new MediaDescriptionCompat.Builder()
                        .setMediaId(MusicLibrary.songId("search:" + query, s.id))
                        .setTitle(s.title).setSubtitle(s.artist).setDescription(s.album)
                        .setIconUri(MusicLibrary.artUri(s.albumId)).build(), MediaItem.FLAG_PLAYABLE));
            }
            result.sendResult(items);
        });
    }

    /** Loads a queue on the worker thread and starts it on the main thread. */
    private void playQueue(QueueLoader loader, boolean shuffle) {
        mWorker.post(() -> {
            final List<MusicLibrary.Song> songs = new ArrayList<>();
            final int index = loader.load(songs);
            mMain.post(() -> {
                if (songs.isEmpty()) return;
                mPlayback.setShuffle(shuffle || mPlayback.shuffle());
                mPlayback.setQueue(songs, Math.max(0, index), 0, true);
            });
        });
    }

    private interface QueueLoader {
        /** Fills 'songs' and returns the index to start at. */
        int load(List<MusicLibrary.Song> songs);
    }

    private final class SessionCallback extends MediaSessionCompat.Callback {
        @Override
        public void onPlay() {
            if (mPlayback.current() == null) {
                playQueue(songs -> {
                    songs.addAll(mLibrary.songs(MusicLibrary.SONGS));
                    return 0;
                }, true);
            } else {
                mPlayback.play();
            }
        }

        @Override
        public void onPause() {
            mPlayback.pause();
        }

        @Override
        public void onStop() {
            mPlayback.stop();
        }

        @Override
        public void onSkipToNext() {
            mPlayback.next();
        }

        @Override
        public void onSkipToPrevious() {
            mPlayback.previous();
        }

        @Override
        public void onSeekTo(long pos) {
            mPlayback.seekTo(pos);
        }

        @Override
        public void onSkipToQueueItem(long id) {
            mPlayback.skipToQueueIndex((int) id);
        }

        @Override
        public void onSetShuffleMode(int mode) {
            mPlayback.setShuffle(mode != PlaybackStateCompat.SHUFFLE_MODE_NONE);
        }

        @Override
        public void onSetRepeatMode(int mode) {
            mPlayback.setRepeat(mode == PlaybackStateCompat.REPEAT_MODE_ONE ? Playback.Repeat.ONE
                    : mode == PlaybackStateCompat.REPEAT_MODE_NONE ? Playback.Repeat.OFF
                    : Playback.Repeat.ALL);
        }

        @Override
        public void onPlayFromMediaId(String mediaId, Bundle extras) {
            if (mediaId.startsWith(MusicLibrary.SHUFFLE)) {
                // Shuffle a whole node, starting at a random song.
                final String node = mediaId.substring(MusicLibrary.SHUFFLE.length());
                playQueue(songs -> {
                    songs.addAll(mLibrary.songs(node));
                    return (int) (Math.random() * songs.size());
                }, true);
                return;
            }
            final String parent = MusicLibrary.parentOf(mediaId);
            final long audioId = MusicLibrary.audioIdOf(mediaId);
            if (parent == null || audioId < 0) return;
            playQueue(songs -> {
                songs.addAll(parent.startsWith("search:")
                        ? mLibrary.search(parent.substring("search:".length()))
                        : mLibrary.songs(parent));
                for (int i = 0; i < songs.size(); ++i) {
                    if (songs.get(i).id == audioId) return i;
                }
                return 0;
            }, false);
        }

        @Override
        public void onCustomAction(String action, Bundle extras) {
            if (ACTION_SHUFFLE.equals(action)) {
                mPlayback.setShuffle(!mPlayback.shuffle());
            } else if (ACTION_REPEAT.equals(action)) {
                mPlayback.setRepeat(Playback.Repeat.values()[
                        (mPlayback.repeat().ordinal() + 1) % Playback.Repeat.values().length]);
            } else if (ACTION_FAVORITE.equals(action)) {
                final MusicLibrary.Song song = mPlayback.current();
                if (song == null) return;
                mWorker.post(() -> {
                    mStore.toggleFavorite(song.id);
                    mMain.post(() -> {
                        updateState();
                        notifyChildrenChanged(MusicLibrary.FAVORITES);
                    });
                });
            }
        }

        @Override
        public void onPlayFromSearch(String query, Bundle extras) {
            // An empty query ("play music") shuffles the library.
            playQueue(songs -> {
                songs.addAll(TextUtils.isEmpty(query) ? mLibrary.songs(MusicLibrary.SONGS)
                        : mLibrary.search(query));
                return 0;
            }, TextUtils.isEmpty(query));
        }
    }

    // Playback.Listener

    @Override
    public void onSongChanged(MusicLibrary.Song song) {
        mSession.setMetadata(song.metadata());
        publishQueue();
        save();
        if (mPlayback.isPlaying()) {
            mWorker.post(() -> {
                mStore.played(song.id);
                mMain.post(() -> notifyChildrenChanged(MusicLibrary.PLAYED));
            });
        }
    }

    @Override
    public void onStateChanged() {
        updateState();
    }

    private void publishQueue() {
        final List<MusicLibrary.Song> queue = mPlayback.queue();
        final int current = mPlayback.currentIndex();
        final int from = Math.max(0, Math.min(current - MAX_QUEUE / 2, queue.size() - MAX_QUEUE));
        final List<MediaSessionCompat.QueueItem> items = new ArrayList<>();
        for (int i = from; i < Math.min(queue.size(), from + MAX_QUEUE); ++i) {
            final MusicLibrary.Song s = queue.get(i);
            items.add(new MediaSessionCompat.QueueItem(new MediaDescriptionCompat.Builder()
                    .setMediaId(String.valueOf(s.id)).setTitle(s.title).setSubtitle(s.artist)
                    .setIconUri(MusicLibrary.artUri(s.albumId)).build(), i));
        }
        mSession.setQueue(items);
        mSession.setQueueTitle(getString(R.string.queue_title));
    }

    private void updateState() {
        final boolean playing = mPlayback.isPlaying();
        final MusicLibrary.Song song = mPlayback.current();
        final boolean favorite = song != null && mStore.isFavorite(song.id);
        final Playback.Repeat repeat = mPlayback.repeat();
        mSession.setPlaybackState(new PlaybackStateCompat.Builder()
                .setActions(ACTIONS)
                .addCustomAction(ACTION_SHUFFLE, getString(mPlayback.shuffle()
                                ? R.string.action_shuffle_on : R.string.action_shuffle_off),
                        mPlayback.shuffle() ? R.drawable.ic_shuffle_on : R.drawable.ic_shuffle_off)
                .addCustomAction(ACTION_REPEAT, getString(repeat == Playback.Repeat.ONE
                                ? R.string.action_repeat_one : repeat == Playback.Repeat.ALL
                                ? R.string.action_repeat_all : R.string.action_repeat_off),
                        repeat == Playback.Repeat.ONE ? R.drawable.ic_repeat_one
                                : repeat == Playback.Repeat.ALL ? R.drawable.ic_repeat_on
                                : R.drawable.ic_repeat_off)
                .addCustomAction(ACTION_FAVORITE, getString(favorite
                                ? R.string.action_unfavorite : R.string.action_favorite),
                        favorite ? R.drawable.ic_favorite_on : R.drawable.ic_favorite_off)
                .setState(song == null ? PlaybackStateCompat.STATE_NONE
                        : playing ? PlaybackStateCompat.STATE_PLAYING : PlaybackStateCompat.STATE_PAUSED,
                        mPlayback.positionMs(), playing ? 1f : 0f)
                .setActiveQueueItemId(Math.max(0, mPlayback.currentIndex()))
                .build());
        mSession.setShuffleMode(mPlayback.shuffle() ? PlaybackStateCompat.SHUFFLE_MODE_ALL
                : PlaybackStateCompat.SHUFFLE_MODE_NONE);
        mSession.setRepeatMode(mPlayback.repeat() == Playback.Repeat.ONE
                ? PlaybackStateCompat.REPEAT_MODE_ONE
                : mPlayback.repeat() == Playback.Repeat.ALL ? PlaybackStateCompat.REPEAT_MODE_ALL
                : PlaybackStateCompat.REPEAT_MODE_NONE);
        mSession.setActive(song != null);
        updateForeground(playing, song);
        if (!playing) save();
    }

    /** Foreground with a media notification while playing, so playback outlives the UI. */
    private void updateForeground(boolean playing, MusicLibrary.Song song) {
        if (playing && song != null) {
            final Notification n = new NotificationCompat.Builder(this, CHANNEL)
                    .setSmallIcon(R.drawable.ic_music)
                    .setContentTitle(song.title)
                    .setContentText(song.artist)
                    .setStyle(new MediaStyle().setMediaSession(mSession.getSessionToken()))
                    .setOngoing(true)
                    .build();
            if (!mForeground) {
                startForegroundService(new Intent(this, MusicService.class));
                startForeground(NOTIFICATION_ID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK);
                mForeground = true;
            } else {
                getSystemService(NotificationManager.class).notify(NOTIFICATION_ID, n);
            }
        } else if (mForeground) {
            stopForeground(STOP_FOREGROUND_REMOVE);
            mForeground = false;
        }
    }

    private void save() {
        final List<MusicLibrary.Song> queue = mPlayback.queue();
        if (queue.isEmpty()) return;
        final List<String> ids = new ArrayList<>();
        final int current = mPlayback.currentIndex();
        final int from = Math.max(0, Math.min(current - MAX_QUEUE / 2, queue.size() - MAX_QUEUE));
        for (int i = from; i < Math.min(queue.size(), from + MAX_QUEUE); ++i) {
            ids.add(String.valueOf(queue.get(i).id));
        }
        getSharedPreferences(PREFS, MODE_PRIVATE).edit()
                .putString(KEY_QUEUE, TextUtils.join(",", ids))
                .putInt(KEY_INDEX, current - from)
                .putLong(KEY_POSITION, mPlayback.positionMs())
                .putBoolean(KEY_SHUFFLE, mPlayback.shuffle())
                .putString(KEY_REPEAT, mPlayback.repeat().name())
                .apply();
    }

    /** Loads the last queue paused at the saved position, so the media card shows it. */
    private void restore() {
        final SharedPreferences prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        final String saved = prefs.getString(KEY_QUEUE, "");
        if (saved.isEmpty()) return;
        final int index = prefs.getInt(KEY_INDEX, 0);
        final long position = prefs.getLong(KEY_POSITION, 0);
        mPlayback.setRepeat(Playback.Repeat.valueOf(prefs.getString(KEY_REPEAT, "OFF")));
        mWorker.post(() -> {
            final List<Long> ids = new ArrayList<>();
            for (String id : saved.split(",")) {
                try {
                    ids.add(Long.parseLong(id));
                } catch (NumberFormatException ignored) {
                    // Skip.
                }
            }
            final List<MusicLibrary.Song> songs = mLibrary.songsById(ids);
            mMain.post(() -> {
                if (songs.isEmpty() || mPlayback.current() != null) return;
                // Songs deleted since: keep the index in range.
                final int i = Math.min(index, songs.size() - 1);
                mPlayback.setQueue(songs, i, position, false);
                mPlayback.setShuffle(prefs.getBoolean(KEY_SHUFFLE, false));
            });
        });
    }
}
