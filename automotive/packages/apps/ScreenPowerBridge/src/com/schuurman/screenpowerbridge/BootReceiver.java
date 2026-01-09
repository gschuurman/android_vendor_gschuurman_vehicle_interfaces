package com.schuurman.screenpowerbridge;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;

public class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        // Start the service when device boots
        context.startForegroundService(new Intent(context, PowerBridgeService.class));
    }
}