package com.schuurman.vim3.volumecontrol;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.media.AudioManager;

public class VolumeControlReceiver extends BroadcastReceiver {

    static final String ACTION_VOLUME_UP   = "com.schuurman.vim3.volumecontrol.VOLUME_UP";
    static final String ACTION_VOLUME_DOWN = "com.schuurman.vim3.volumecontrol.VOLUME_DOWN";
    static final String ACTION_VOLUME_MUTE = "com.schuurman.vim3.volumecontrol.VOLUME_MUTE";

    @Override
    public void onReceive(Context context, Intent intent) {
        if (intent.getAction() == null) return;

        AudioManager am = (AudioManager) context.getSystemService(Context.AUDIO_SERVICE);
        if (am == null) return;

        switch (intent.getAction()) {
            case ACTION_VOLUME_UP:
                am.adjustStreamVolume(AudioManager.STREAM_MUSIC,
                        AudioManager.ADJUST_RAISE, AudioManager.FLAG_SHOW_UI);
                break;
            case ACTION_VOLUME_DOWN:
                am.adjustStreamVolume(AudioManager.STREAM_MUSIC,
                        AudioManager.ADJUST_LOWER, AudioManager.FLAG_SHOW_UI);
                break;
            case ACTION_VOLUME_MUTE:
                am.adjustStreamVolume(AudioManager.STREAM_MUSIC,
                        AudioManager.ADJUST_TOGGLE_MUTE, AudioManager.FLAG_SHOW_UI);
                break;
        }
    }
}
