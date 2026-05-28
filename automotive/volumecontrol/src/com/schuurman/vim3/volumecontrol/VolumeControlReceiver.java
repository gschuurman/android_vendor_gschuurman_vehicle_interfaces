package com.schuurman.vim3.volumecontrol;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.media.AudioManager;

/**
 * Handles volume up / down / mute broadcasts sent by CarSystemBarButton.
 * Uses FLAG=0 so no volume panel appears — safe for driving.
 */
public class VolumeControlReceiver extends BroadcastReceiver {

    static final String ACTION_VOLUME_UP   = "com.schuurman.vim3.volumecontrol.VOLUME_UP";
    static final String ACTION_VOLUME_DOWN = "com.schuurman.vim3.volumecontrol.VOLUME_DOWN";
    static final String ACTION_VOLUME_MUTE = "com.schuurman.vim3.volumecontrol.VOLUME_MUTE";

    @Override
    public void onReceive(Context context, Intent intent) {
        AudioManager am = context.getSystemService(AudioManager.class);
        if (am == null || intent.getAction() == null) return;

        int direction;
        switch (intent.getAction()) {
            case ACTION_VOLUME_UP:
                direction = AudioManager.ADJUST_RAISE;
                break;
            case ACTION_VOLUME_DOWN:
                direction = AudioManager.ADJUST_LOWER;
                break;
            case ACTION_VOLUME_MUTE:
                direction = AudioManager.ADJUST_TOGGLE_MUTE;
                break;
            default:
                return;
        }
        am.adjustStreamVolume(AudioManager.STREAM_MUSIC, direction, 0 /* no UI */);
    }
}
