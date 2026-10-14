package com.gschuurman.carmusic;

import android.os.Bundle;
import android.os.Handler;
import android.os.HandlerThread;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

import androidx.fragment.app.FragmentActivity;

import com.android.car.ui.core.CarUi;
import com.android.car.ui.toolbar.NavButtonMode;
import com.android.car.ui.toolbar.ToolbarController;

import java.util.List;

/**
 * Import music from USB storage: lists the mounted USB volumes with the number of audio files on
 * them, and shows the progress and result of a running import.
 */
public final class ImportActivity extends FragmentActivity implements ImportService.Observer {
    private LinearLayout mVolumes;
    private View mProgressGroup;
    private TextView mProgressText;
    private ProgressBar mProgress;
    private TextView mStatus;
    private Handler mWorker;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_import);
        final ToolbarController toolbar = CarUi.requireToolbar(this);
        toolbar.setTitle(R.string.import_title);
        toolbar.setNavButtonMode(NavButtonMode.BACK);

        mVolumes = findViewById(R.id.volumes);
        mProgressGroup = findViewById(R.id.progress_group);
        mProgressText = findViewById(R.id.progress_text);
        mProgress = findViewById(R.id.progress);
        mStatus = findViewById(R.id.status);
        ((Button) findViewById(R.id.cancel)).setOnClickListener(v -> ImportService.cancel(this));

        final HandlerThread thread = new HandlerThread("CarMusicScan");
        thread.start();
        mWorker = new Handler(thread.getLooper());
        ImportService.createChannel(this);
    }

    @Override
    protected void onResume() {
        super.onResume();
        ImportService.addObserver(this);
        refreshVolumes();
    }

    @Override
    protected void onPause() {
        ImportService.removeObserver(this);
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        mWorker.getLooper().quitSafely();
        super.onDestroy();
    }

    private void refreshVolumes() {
        mVolumes.removeAllViews();
        final List<UsbMusic.Volume> volumes = UsbMusic.volumes(this);
        if (volumes.isEmpty()) {
            mStatus.setText(R.string.import_no_usb);
            return;
        }
        mStatus.setText(R.string.import_pick);
        for (UsbMusic.Volume volume : volumes) {
            final View row = getLayoutInflater().inflate(R.layout.item_volume, mVolumes, false);
            ((TextView) row.findViewById(R.id.label)).setText(volume.label);
            final TextView count = row.findViewById(R.id.count);
            final Button button = row.findViewById(R.id.import_button);
            count.setText(R.string.import_scanning);
            button.setEnabled(false);
            button.setOnClickListener(v -> ImportService.start(this, volume));
            mVolumes.addView(row);
            mWorker.post(() -> {
                final int n = UsbMusic.scan(volume.root).size();
                runOnUiThread(() -> {
                    count.setText(getResources().getQuantityString(R.plurals.song_count, n, n));
                    button.setEnabled(n > 0 && !ImportService.state().running);
                });
            });
        }
    }

    @Override
    public void onImportState(ImportService.State state) {
        mProgressGroup.setVisibility(state.running ? View.VISIBLE : View.GONE);
        mVolumes.setEnabled(!state.running);
        for (int i = 0; i < mVolumes.getChildCount(); ++i) {
            mVolumes.getChildAt(i).findViewById(R.id.import_button).setEnabled(!state.running);
        }
        if (state.running) {
            mProgress.setIndeterminate(state.total == 0);
            mProgress.setMax(Math.max(1, state.total));
            mProgress.setProgress(state.done);
            mProgressText.setText(state.total == 0 ? getString(R.string.import_scanning)
                    : getString(R.string.import_progress, state.done, state.total));
        } else if (state.result != null) {
            mStatus.setText(getString(R.string.import_result, state.result.copied,
                    state.result.skipped, state.result.failed));
        }
    }
}
