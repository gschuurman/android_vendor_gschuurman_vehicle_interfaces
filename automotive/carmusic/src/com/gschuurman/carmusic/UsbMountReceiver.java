package com.gschuurman.carmusic;

import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

import androidx.core.app.NotificationCompat;

import java.io.File;

/** When USB storage with music is mounted, offers to import it (notification). */
public final class UsbMountReceiver extends BroadcastReceiver {
    private static final int NOTIFICATION_ID = 4;

    @Override
    public void onReceive(Context context, Intent intent) {
        if (intent.getData() == null || intent.getData().getPath() == null) return;
        final File root = new File(intent.getData().getPath());
        final PendingResult pending = goAsync();
        new Thread(() -> {
            try {
                for (UsbMusic.Volume volume : UsbMusic.volumes(context)) {
                    if (!volume.root.equals(root)) continue;
                    final int n = UsbMusic.audioCount(UsbMusic.scan(root));
                    if (n == 0) return;
                    ImportService.createChannel(context);
                    final PendingIntent open = PendingIntent.getActivity(context, 0,
                            new Intent(context, ImportActivity.class), PendingIntent.FLAG_IMMUTABLE);
                    context.getSystemService(NotificationManager.class).notify(NOTIFICATION_ID,
                            new NotificationCompat.Builder(context, ImportService.CHANNEL)
                                    .setSmallIcon(R.drawable.ic_music)
                                    .setContentTitle(context.getString(R.string.usb_found_title, volume.label))
                                    .setContentText(context.getResources().getQuantityString(
                                            R.plurals.usb_found_text, n, n))
                                    .setContentIntent(open)
                                    .addAction(0, context.getString(R.string.import_action), open)
                                    .setAutoCancel(true)
                                    .build());
                }
            } finally {
                pending.finish();
            }
        }, "CarMusicUsbScan").start();
    }
}
