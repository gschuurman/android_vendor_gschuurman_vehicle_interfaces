package com.schuurman.vim3.volumecontrol;

import android.car.Car;
import android.car.media.CarAudioManager;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.media.AudioAttributes;

public class VolumeControlReceiver extends BroadcastReceiver {

    static final String ACTION_VOLUME_UP   = "com.schuurman.vim3.volumecontrol.VOLUME_UP";
    static final String ACTION_VOLUME_DOWN = "com.schuurman.vim3.volumecontrol.VOLUME_DOWN";
    static final String ACTION_VOLUME_MUTE = "com.schuurman.vim3.volumecontrol.VOLUME_MUTE";

    @Override
    public void onReceive(Context context, Intent intent) {
        if (intent.getAction() == null) return;

        Car car = Car.createCar(context);
        if (car == null) return;
        try {
            CarAudioManager cam = (CarAudioManager) car.getCarManager(Car.AUDIO_SERVICE);
            if (cam == null) return;

            int groupId = cam.getVolumeGroupIdForUsage(AudioAttributes.USAGE_MEDIA);

            switch (intent.getAction()) {
                case ACTION_VOLUME_UP: {
                    int current = cam.getGroupVolume(groupId);
                    int max = cam.getGroupMaxVolume(groupId);
                    cam.setGroupVolume(groupId, Math.min(current + 1, max), 0);
                    break;
                }
                case ACTION_VOLUME_DOWN: {
                    int current = cam.getGroupVolume(groupId);
                    int min = cam.getGroupMinVolume(groupId);
                    cam.setGroupVolume(groupId, Math.max(current - 1, min), 0);
                    break;
                }
                case ACTION_VOLUME_MUTE: {
                    boolean muted = cam.isVolumeGroupMuted(CarAudioManager.PRIMARY_AUDIO_ZONE, groupId);
                    cam.setVolumeGroupMute(CarAudioManager.PRIMARY_AUDIO_ZONE, groupId, !muted, 0);
                    break;
                }
            }
        } finally {
            car.disconnect();
        }
    }
}
