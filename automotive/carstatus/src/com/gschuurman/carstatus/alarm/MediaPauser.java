package com.gschuurman.carstatus.alarm;

import android.app.ActivityManager;
import android.content.Context;
import android.media.session.MediaController;
import android.media.session.MediaSessionManager;
import android.media.session.PlaybackState;
import android.os.UserHandle;
import android.util.Log;

import java.util.List;

/**
 * Pauses whatever plays for the driver. The alarm service runs in the system user (persistent),
 * the media apps in the current (driver) user, so this asks MediaSessionManager for that user's
 * sessions (MEDIA_CONTENT_CONTROL + INTERACT_ACROSS_USERS_FULL, platform signed).
 */
final class MediaPauser {
    private static final String TAG = "CarStatusAlarm";

    private MediaPauser() {}

    /** Returns how many playing sessions were asked to pause. */
    static int pauseAll(Context context) {
        MediaSessionManager msm = context.getSystemService(MediaSessionManager.class);
        if (msm == null) return 0;
        int user = -1;
        int paused = 0;
        try {
            user = ActivityManager.getCurrentUser();
            List<MediaController> sessions = msm.getActiveSessionsForUser(null, UserHandle.of(user));
            for (MediaController c : sessions) {
                PlaybackState s = c.getPlaybackState();
                if (s == null) continue;
                int st = s.getState();
                if (st == PlaybackState.STATE_PLAYING || st == PlaybackState.STATE_BUFFERING
                        || st == PlaybackState.STATE_FAST_FORWARDING || st == PlaybackState.STATE_REWINDING) {
                    c.getTransportControls().pause();
                    paused++;
                    Log.i(TAG, "Paused " + c.getPackageName());
                }
            }
        } catch (Throwable e) {
            Log.e(TAG, "Cannot pause media for user " + user, e);
        }
        return paused;
    }
}
