/* ==========================================================================
   NAVIGATION — Cambio de vistas, filtros, URL state, navegación secondary.
   Dependencias: utils.js, logos.js, state.js
   ========================================================================== */

function versionedAsset(path, tag) {
    const version = document.body.dataset.assetsV || "dev";
    return `${path}?v=${encodeURIComponent(version)}-${tag}`;
}

const VIEW_STYLES = {
    CONTEST: [
        ["view-contest-styles", versionedAsset("/static/css/pages/contest.css", "contest-9")],
        ["view-profile-styles", versionedAsset("/static/css/pages/profile.css", "profile-4")],
    ],
    STANDINGS: [["view-standings-styles", versionedAsset("/static/css/pages/standings.css", "standings-5")]],
    LIVE: [
        ["view-match-card-styles", versionedAsset("/static/css/components/match_cards.css", "matches-5")],
        ["view-direct-styles", versionedAsset("/static/css/pages/direct.css", "direct-3")],
    ],
    LEAGUES: [
        ["view-match-card-styles", versionedAsset("/static/css/components/match_cards.css", "matches-5")],
        ["view-direct-styles", versionedAsset("/static/css/pages/direct.css", "direct-3")],
    ],
    SNAKE: [["view-games-styles", versionedAsset("/static/css/pages/games.css", "games-7")]],
    QUIZ: [["view-quiz-styles", versionedAsset("/static/css/pages/quiz_page.css", "quiz-page-3")]],
    TICKET: [
        ["view-ticket-styles", versionedAsset("/static/css/pages/ticket.css", "ticket-5")],
        ["view-ticket-compact-styles", versionedAsset("/static/css/pages/ticket_compact.css", "ticket-compact-8")],
        ["view-pleno-modal-styles", versionedAsset("/static/css/components/pleno_modal.css", "pleno-modal-2")],
    ],
};

const VIEW_SCRIPTS = {
    ALL: [["view-cover-script", versionedAsset("/static/js/pages/cover_page.js", "cover-page-65-p19")]],
    CONTEST: [["view-contest-script", versionedAsset("/static/js/contest.js", "contest-9")]],
    STANDINGS: [["view-standings-script", versionedAsset("/static/js/standings.js", "standings-6")]],
    SNAKE: [["view-games-script", versionedAsset("/static/js/pages/games_hub.js", "games-hub-10")]],
    QUIZ: [["view-quiz-script", versionedAsset("/static/js/quiz.js", "quiz-2")]],
    TICKET: [
        ["view-ticket-script", versionedAsset("/static/js/pages/ticket_page.js", "ticket-page-7")],
        ["view-pleno-modal-script", versionedAsset("/static/js/components/pleno_modal.js", "pleno-modal-2")],
    ],
};
