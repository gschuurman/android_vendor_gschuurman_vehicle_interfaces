package com.schuurman.vim3.volumecontrol;

import static android.media.AudioAttributes.USAGE_MEDIA;

import android.car.Car;
import android.car.media.CarAudioManager;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;

/**
 * Adjusts the primary zone media volume in response to the system bar volume buttons.
 *
 * <p>This must go through {@link CarAudioManager} volume groups. On AAOS the legacy
 * {@link android.media.AudioManager#adjustStreamVolume} call is a no-op because
 * CarAudioService owns volume via car volume groups, which is why the buttons did
 * nothing before.
 */
public class VolumeControlReceiver extends BroadcastReceiver {

    private static final String TAG = "VolumeControlReceiver";

    static final String ACTION_VOLUME_UP   = "com.schuurman.vim3.volumecontrol.VOLUME_UP";
    static final String ACTION_VOLUME_DOWN = "com.schuurman.vim3.volumecontrol.VOLUME_DOWN";
    static final String ACTION_VOLUME_MUTE = "com.schuurman.vim3.volumecontrol.VOLUME_MUTE";

    // Match the previous design: adjust silently, no system volume panel.
    private static final int FLAGS = 0;

    @Override
    public void onReceive(Context context, Intent intent) {
        String action = intent.getAction();
        if (action == null) return;

        // Car.createCar() binds to the car service, which is not allowed from a
        // BroadcastReceiver's restricted context, and the connect blocks. So hop to the
        // application context (can bind services) and run off the main thread via goAsync().
        final Context appContext = context.getApplicationContext();
        final PendingResult pending = goAsync();
        new Thread(() -> {
            try {
                adjustVolume(appContext, action);
            } finally {
                pending.finish();
            }
        }, "VolumeControl").start();
    }

    private static void adjustVolume(Context context, String action) {
        Car car = null;
        try {
            car = Car.createCar(context);
            CarAudioManager am = (CarAudioManager) car.getCarManager(Car.AUDIO_SERVICE);
            if (am == null) {
                Log.w(TAG, "CarAudioManager unavailable");
                return;
            }

            int zoneId = CarAudioManager.PRIMARY_AUDIO_ZONE;
            int groupId = am.getVolumeGroupIdForUsage(zoneId, USAGE_MEDIA);

            switch (action) {
                case ACTION_VOLUME_UP: {
                    int max = am.getGroupMaxVolume(zoneId, groupId);
                    int cur = am.getGroupVolume(zoneId, groupId);
                    am.setGroupVolume(zoneId, groupId, Math.min(cur + 1, max), FLAGS);
                    break;
                }
                case ACTION_VOLUME_DOWN: {
                    int min = am.getGroupMinVolume(zoneId, groupId);
                    int cur = am.getGroupVolume(zoneId, groupId);
                    am.setGroupVolume(zoneId, groupId, Math.max(cur - 1, min), FLAGS);
                    break;
                }
                case ACTION_VOLUME_MUTE: {
                    boolean muted = am.isVolumeGroupMuted(zoneId, groupId);
                    am.setVolumeGroupMute(zoneId, groupId, !muted, FLAGS);
                    break;
                }
                default:
                    break;
            }
        } catch (Exception e) {
            Log.e(TAG, "Failed to adjust car volume for " + action, e);
        } finally {
            if (car != null) {
                car.disconnect();
            }
        }
    }
}
