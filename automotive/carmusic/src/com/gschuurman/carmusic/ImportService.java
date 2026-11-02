package com.gschuurman.carmusic;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;

import androidx.core.app.NotificationCompat;

import java.io.File;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;

/** Copies the music of one USB volume into the Music folder, as a foreground service. */
public final class ImportService extends Service {
    static final String EXTRA_ROOT = "root";
    static final String EXTRA_LABEL = "label";
    private static final String ACTION_CANCEL = "com.gschuurman.carmusic.CANCEL_IMPORT";
    static final String CHANNEL = "import";
    private static final int NOTIFICATION_ID = 2;
    private static final int RESULT_NOTIFICATION_ID = 3;

    /** Import state for the UI. */
    static final class State {
        boolean running;
        String label = "";
        int done, total;
        UsbMusic.Result result;
    }

    /** Observes the import state; calls arrive on the main thread. */
    interface Observer {
        void onImportState(State state);
    }

    private static final State sState = new State();
    private static final List<Observer> sObservers = new CopyOnWriteArrayList<>();
    private static final Handler sMain = new Handler(Looper.getMainLooper());

    private volatile boolean mCancelled;

    static State state() {
        return sState;
    }

    static void addObserver(Observer o) {
        sObservers.add(o);
        o.onImportState(sState);
    }

    static void removeObserver(Observer o) {
        sObservers.remove(o);
    }

    private static void publish() {
        sMain.post(() -> {
            for (Observer o : sObservers) o.onImportState(sState);
        });
    }

    static void start(Context context, UsbMusic.Volume volume) {
        context.startForegroundService(new Intent(context, ImportService.class)
                .putExtra(EXTRA_ROOT, volume.root.getPath())
                .putExtra(EXTRA_LABEL, volume.label));
    }

    static void cancel(Context context) {
        context.startService(new Intent(context, ImportService.class).setAction(ACTION_CANCEL));
    }

    static void createChannel(Context context) {
        context.getSystemService(NotificationManager.class).createNotificationChannel(
                new NotificationChannel(CHANNEL, context.getString(R.string.channel_import),
                        NotificationManager.IMPORTANCE_DEFAULT));
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACTION_CANCEL.equals(intent.getAction())) {
            mCancelled = true;
            return START_NOT_STICKY;
        }
        createChannel(this);
        startForeground(NOTIFICATION_ID, progressNotification(0, 0),
                ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC);
        if (sState.running || intent == null) return START_NOT_STICKY;
        final File root = new File(intent.getStringExtra(EXTRA_ROOT));
        sState.running = true;
        sState.label = intent.getStringExtra(EXTRA_LABEL);
        sState.done = sState.total = 0;
        sState.result = null;
        mCancelled = false;
        publish();
        new Thread(() -> runImport(root), "CarMusicImport").start();
        return START_NOT_STICKY;
    }

    private void runImport(File root) {
        final List<UsbMusic.Track> tracks = UsbMusic.scan(root);
        final NotificationManager nm = getSystemService(NotificationManager.class);
        final UsbMusic.Result result = UsbMusic.copy(this, tracks, new UsbMusic.Progress() {
            @Override
            public void onProgress(int done, int total, UsbMusic.Track current) {
                sState.done = done;
                sState.total = total;
                publish();
                nm.notify(NOTIFICATION_ID, progressNotification(done, total));
            }

            @Override
            public boolean isCancelled() {
                return mCancelled;
            }
        });
        sState.running = false;
        sState.result = result;
        publish();
        if (result.copied > 0) CoverFetchJob.schedule(this, true);
        nm.notify(RESULT_NOTIFICATION_ID, new NotificationCompat.Builder(this, CHANNEL)
                .setSmallIcon(R.drawable.ic_music)
                .setContentTitle(getString(mCancelled ? R.string.import_cancelled : R.string.import_done))
                .setContentText(getString(R.string.import_result, result.copied, result.skipped,
                        result.failed))
                .setContentIntent(activityIntent())
                .setAutoCancel(true)
                .build());
        stopForeground(STOP_FOREGROUND_REMOVE);
        stopSelf();
    }

    private Notification progressNotification(int done, int total) {
        return new NotificationCompat.Builder(this, CHANNEL)
                .setSmallIcon(R.drawable.ic_music)
                .setContentTitle(getString(R.string.import_running, sState.label))
                .setContentText(total == 0 ? getString(R.string.import_scanning)
                        : getString(R.string.import_progress, done, total))
                .setProgress(total, done, total == 0)
                .setOngoing(true)
                .setOnlyAlertOnce(true)
                .setContentIntent(activityIntent())
                .build();
    }

    private PendingIntent activityIntent() {
        return PendingIntent.getActivity(this, 0, new Intent(this, ImportActivity.class),
                PendingIntent.FLAG_IMMUTABLE);
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
