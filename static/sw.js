self.addEventListener('push', function (event) {
    var data = {};
    try { data = event.data ? event.data.json() : {}; } catch (e) {}
    var title = data.title || 'SmartStride reminder';
    var options = {
        body: data.body || 'You have a calendar reminder.',
        tag: data.tag || 'studyos-reminder',
        data: { url: data.url || '/calendar#today' },
        requireInteraction: true,
        renotify: true
    };
    event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', function (event) {
    event.notification.close();
    var url = (event.notification.data && event.notification.data.url) || '/calendar#today';
    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (windows) {
            for (var i = 0; i < windows.length; i++) {
                var client = windows[i];
                if (client.url.indexOf(self.location.origin) === 0) {
                    client.navigate(url);
                    return client.focus();
                }
            }
            return clients.openWindow(url);
        })
    );
});
