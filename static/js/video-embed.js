// Click-to-play for YouTube cards: swaps the cover for the player only after a click,
// so visiting a page does not contact YouTube or autoplay anything.
(function () {
    document.addEventListener("click", function (event) {
        var link = event.target.closest(".video-play");
        var frame = link && link.closest("[data-video-embed]");
        if (!frame || !frame.dataset.videoEmbed) return;
        event.preventDefault();
        var player = document.createElement("iframe");
        player.src = frame.dataset.videoEmbed;
        player.title = frame.dataset.videoTitle || "Видео";
        player.allow = "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share";
        player.referrerPolicy = "strict-origin-when-cross-origin";
        player.allowFullscreen = true;
        frame.replaceChildren(player);
        player.focus();
    });
})();
