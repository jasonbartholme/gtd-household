// Listen for incoming push messages
self.addEventListener('push', function(event) {
    let data = { title: 'App Alert', body: 'You have a new notification.', url: '/' };
    if (event.data) {
        try {
            data = { ...data, ...event.data.json() };
        } catch (e) {
            data.body = event.data.text();
        }
    }

    const options = {
        body: data.body,
        icon: '/static/images/favicon-32x32.png', // Optional: Path to your app icon
        badge: '/static/images/favicon-16x16.png', // Optional: Small monochromatic icon for Android
        data: { url: data.url }
    };

    event.waitUntil(
        self.registration.showNotification(data.title, options)
    );
});

// Handle clicks on the notification
self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    const url = (event.notification.data && event.notification.data.url) || '/';
    event.waitUntil(
        clients.openWindow(url)
    );
});