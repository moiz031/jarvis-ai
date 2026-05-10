package com.jarvis.native

import android.app.Service
import android.content.Intent
import android.os.IBinder
import android.util.Log

class JarvisBackgroundService : Service() {
    private val TAG = "JarvisService"

    override fun onCreate() {
        super.onCreate()
        Log.d(TAG, "Jarvis Background Service Created")
        // Initialize wake-word detector or other background tasks here
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        Log.d(TAG, "Jarvis Background Service Started")
        // Keep service running
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? {
        return null
    }

    override fun onDestroy() {
        Log.d(TAG, "Jarvis Background Service Destroyed")
        super.onDestroy()
    }
}
