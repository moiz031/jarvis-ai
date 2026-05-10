package com.jarvis.native

import android.accessibilityservice.AccessibilityService
import android.view.accessibility.AccessibilityEvent
import android.util.Log

class JarvisAccessibilityService : AccessibilityService() {
    private val TAG = "JarvisAccessibility"

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        // This is where we capture screen content or intercept UI events
        Log.d(TAG, "Accessibility Event: ${event?.eventType}")
    }

    override fun onInterrupt() {
        Log.w(TAG, "Accessibility Service Interrupted")
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        Log.d(TAG, "Accessibility Service Connected")
    }
}
