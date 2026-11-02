package com.gschuurman.carmusic;

import android.content.Context;
import android.media.AudioAttributes;
import android.media.AudioFocusRequest;
import android.media.AudioManager;
import android.media.MediaPlayer;
import android.os.PowerManager;
import android.util.Log;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Random;

/**
 * Plays a queue of library songs with MediaPlayer: next/previous, seek, shuffle (a shuffled play
 * order over the queue) and repeat (off/all/one), with audio focus for USAGE_MEDIA.
 */
final class Playback implements AudioManager.OnAudioFocusChangeListener {
    private static final String TAG = "CarMusic";
    /** Previous restarts the song instead after this much of it has played. */
    private static final long RESTART_THRESHOLD_MS = 3000;

    enum Repeat { OFF, ALL, ONE }

    /** Playback state changes, for the media session. */
    interface Listener {
        void onSongChanged(MusicLibrary.Song song);
        void onStateChanged();
    }

    private final Context mContext;
    private final Listener mListener;
    private final AudioManager mAudioManager;
    private final AudioFocusRequest mFocusRequest;
    private final AudioAttributes mAttributes = new AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_MEDIA)
            .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
            .build();

    private List<MusicLibrary.Song> mQueue = new ArrayList<>();
    /** Play order: indexes into mQueue (identity unless shuffled). */
    private List<Integer> mOrder = new ArrayList<>();
    private int mPosition = -1;  // index into mOrder
    private boolean mShuffle;
    private Repeat mRepeat = Repeat.OFF;

    private MediaPlayer mPlayer;
    private boolean mPrepared;
    private boolean mPlayWhenReady;
    private long mPendingSeekMs;
    private boolean mResumeOnFocusGain;

    Playback(Context context, Listener listener) {
        mContext = context;
        mListener = listener;
        mAudioManager = context.getSystemService(AudioManager.class);
        mFocusRequest = new AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN)
                .setAudioAttributes(mAttributes)
                .setOnAudioFocusChangeListener(this)
                .setWillPauseWhenDucked(false)
                .build();
    }

    List<MusicLibrary.Song> queue() {
        return mQueue;
    }

    /** Index into queue() of the current song, or -1. */
    int currentIndex() {
        return mPosition >= 0 && mPosition < mOrder.size() ? mOrder.get(mPosition) : -1;
    }

    MusicLibrary.Song current() {
        final int i = currentIndex();
        return i >= 0 ? mQueue.get(i) : null;
    }

    boolean isPlaying() {
        return mPlayWhenReady;
    }

    boolean shuffle() {
        return mShuffle;
    }

    Repeat repeat() {
        return mRepeat;
    }

    long positionMs() {
        if (mPlayer != null && mPrepared) return mPlayer.getCurrentPosition();
        return mPendingSeekMs;
    }

    /** Replaces the queue and loads queue[index]; plays it if 'play'. */
    void setQueue(List<MusicLibrary.Song> songs, int index, long positionMs, boolean play) {
        mQueue = new ArrayList<>(songs);
        buildOrder(index);
        mPosition = mShuffle ? 0 : index;
        load(positionMs, play);
    }

    void setShuffle(boolean shuffle) {
        if (shuffle == mShuffle) return;
        final int current = currentIndex();
        mShuffle = shuffle;
        buildOrder(current);
        mPosition = mOrder.indexOf(current);
        mListener.onStateChanged();
    }

    void setRepeat(Repeat repeat) {
        mRepeat = repeat;
        mListener.onStateChanged();
    }

    void play() {
        if (current() == null) return;
        if (mPlayer == null) {
            load(mPendingSeekMs, true);
            return;
        }
        if (!requestFocus()) return;
        mPlayWhenReady = true;
        if (mPrepared) mPlayer.start();
        mListener.onStateChanged();
    }

    void pause() {
        mPlayWhenReady = false;
        mResumeOnFocusGain = false;
        if (mPlayer != null && mPrepared && mPlayer.isPlaying()) mPlayer.pause();
        mListener.onStateChanged();
    }

    void stop() {
        pause();
        release();
        mAudioManager.abandonAudioFocusRequest(mFocusRequest);
        mListener.onStateChanged();
    }

    void seekTo(long ms) {
        if (mPlayer != null && mPrepared) {
            mPlayer.seekTo(ms, MediaPlayer.SEEK_PREVIOUS_SYNC);
        } else {
            mPendingSeekMs = ms;
        }
        mListener.onStateChanged();
    }

    void skipToQueueIndex(int index) {
        if (index < 0 || index >= mQueue.size()) return;
        mPosition = mOrder.indexOf(index);
        load(0, true);
    }

    void next() {
        if (mOrder.isEmpty()) return;
        if (mPosition + 1 < mOrder.size()) {
            mPosition++;
        } else if (mRepeat != Repeat.OFF) {
            mPosition = 0;
        } else {
            return;
        }
        load(0, mPlayWhenReady);
    }

    void previous() {
        if (mOrder.isEmpty()) return;
        if (positionMs() > RESTART_THRESHOLD_MS || mPosition == 0) {
            seekTo(0);
            return;
        }
        mPosition--;
        load(0, mPlayWhenReady);
    }

    void release() {
        if (mPlayer != null) {
            mPlayer.release();
            mPlayer = null;
        }
        mPrepared = false;
    }

    private void buildOrder(int first) {
        mOrder = new ArrayList<>();
        for (int i = 0; i < mQueue.size(); ++i) mOrder.add(i);
        if (mShuffle && !mOrder.isEmpty()) {
            Collections.shuffle(mOrder, new Random());
            // The current song starts the shuffled order.
            if (first >= 0) {
                mOrder.remove(Integer.valueOf(first));
                mOrder.add(0, first);
            }
        }
    }

    private void load(long positionMs, boolean play) {
        release();
        final MusicLibrary.Song song = current();
        mPendingSeekMs = positionMs;
        mPlayWhenReady = play;
        if (song == null) {
            mListener.onStateChanged();
            return;
        }
        mListener.onSongChanged(song);
        if (play && !requestFocus()) mPlayWhenReady = false;

        final MediaPlayer player = new MediaPlayer();
        mPlayer = player;
        player.setAudioAttributes(mAttributes);
        player.setWakeMode(mContext, PowerManager.PARTIAL_WAKE_LOCK);
        player.setOnPreparedListener(p -> {
            if (p != mPlayer) return;
            mPrepared = true;
            if (mPendingSeekMs > 0) p.seekTo(mPendingSeekMs, MediaPlayer.SEEK_PREVIOUS_SYNC);
            mPendingSeekMs = 0;
            if (mPlayWhenReady) p.start();
            mListener.onStateChanged();
        });
        player.setOnCompletionListener(p -> {
            if (p != mPlayer) return;
            if (mRepeat == Repeat.ONE) {
                p.seekTo(0);
                p.start();
            } else if (mPosition + 1 < mOrder.size() || mRepeat == Repeat.ALL) {
                next();
            } else {
                mPlayWhenReady = false;
                mPosition = 0;
                load(0, false);
            }
        });
        player.setOnErrorListener((p, what, extra) -> {
            Log.w(TAG, "Can't play " + song.uri() + ": " + what + "/" + extra);
            if (p == mPlayer && mPosition + 1 < mOrder.size()) next(); else pause();
            return true;
        });
        try {
            player.setDataSource(mContext, song.uri());
            player.prepareAsync();
        } catch (IOException | RuntimeException e) {
            Log.w(TAG, "Can't open " + song.uri(), e);
            mPlayWhenReady = false;
        }
        mListener.onStateChanged();
    }

    private boolean requestFocus() {
        return mAudioManager.requestAudioFocus(mFocusRequest) == AudioManager.AUDIOFOCUS_REQUEST_GRANTED;
    }

    @Override
    public void onAudioFocusChange(int change) {
        switch (change) {
            case AudioManager.AUDIOFOCUS_GAIN:
                if (mResumeOnFocusGain) {
                    mResumeOnFocusGain = false;
                    play();
                }
                break;
            case AudioManager.AUDIOFOCUS_LOSS_TRANSIENT_CAN_DUCK:
                // Navigation prompts: CarAudioService ducks the music itself.
                break;
            case AudioManager.AUDIOFOCUS_LOSS_TRANSIENT:
                // Calls, voice assistant: pause and pick up afterwards.
                if (mPlayWhenReady) {
                    pause();
                    mResumeOnFocusGain = true;
                }
                break;
            case AudioManager.AUDIOFOCUS_LOSS:
                pause();
                break;
            default:
                break;
        }
    }
}
