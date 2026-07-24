/* ==========================================================================
   LOGOS — Escudos, tokens de equipo, alias y renderizado de celdas de equipo.
   Dependencias: utils.js (normalizeName, escapeHtml, getShortName)
   ========================================================================== */

function teamToken(name) {
    const short = getShortName(name);
    const cleaned = short.replace(/[^A-Z0-9]/g, "");
    return cleaned.slice(0, 2) || "--";
}

function teamLogo(match, side) {
    if (!match) return "";
    const teamName = side === "home"
        ? (match.local || match.home_name || match.home?.name || "")
        : (match.visitante || match.away_name || match.away?.name || "");
    const direct = side === "home"
        ? (match.logo_local || match.home_logo || match.home?.logo || "")
        : (match.logo_visitante || match.away_logo || match.away?.logo || "");
    return direct || fixedTeamLogo(teamName);
}

function fixedTeamLogo(name) {
    const cacheKey = logoLookupKey(name);
    if (logoCache.has(cacheKey)) return logoCache.get(cacheKey);
    const result = TEAM_LOGO_FILES[cacheKey] || "";
    logoCache.set(cacheKey, result);
    return result;
}

const TEAM_LOGO_ALIASES = {
    "FC BARCELONA": "BARCELONA",
    "F C BARCELONA": "BARCELONA",
    "BARCA": "BARCELONA",
    "VILLARREAL CF": "VILLARREAL",
    "VILLARREAL C F": "VILLARREAL",
    "CLUB ATLETICO DE MADRID": "ATLETICO MADRID",
    "ATLETICO DE MADRID": "ATLETICO MADRID",
    "AT MADRID": "ATLETICO MADRID",
    "AT. MADRID": "ATLETICO MADRID",
    "GETAFE CF": "GETAFE",
    "VALENCIA CF": "VALENCIA",
    "ELCHE CF": "ELCHE",
    "LEVANTE UD": "LEVANTE",
    "CA OSASUNA": "OSASUNA",
    "CLUB ATLETICO OSASUNA": "OSASUNA",
    "RCD MALLORCA": "MALLORCA",
    "R C D MALLORCA": "MALLORCA",
    "GIRONA FC": "GIRONA",
    "MALAGA CF": "MALAGA",
    "RC DEPORTIVO": "DEPORTIVO LA CORUNA",
    "REAL CLUB DEPORTIVO": "DEPORTIVO LA CORUNA",
    "DEPORTIVO": "DEPORTIVO LA CORUNA",
    "R RACING CLUB": "RACING SANTANDER",
    "R. RACING CLUB": "RACING SANTANDER",
    "RACING CLUB": "RACING SANTANDER",
    "REAL RACING CLUB DE SANTANDER": "RACING SANTANDER",
    "R SANTANDER": "RACING SANTANDER",
    "R. SANTANDER": "RACING SANTANDER",
    "CADIZ CF": "CADIZ",
    "RCD ESPANYOL DE BARCELONA": "RCD ESPANYOL",
    "REAL CLUB DEPORTIVO ESPANYOL": "RCD ESPANYOL",
    "UD ALMERIA": "ALMERIA",
    "CD CASTELLON": "CASTELLON",
    "BURGOS CF": "BURGOS",
    "SD EIBAR": "EIBAR",
    "CORDOBA CF": "CORDOBA",
    "ALBACETE BP": "ALBACETE",
    "ALBACETE BALOMP": "ALBACETE",
    "REAL SPORTING": "SPORTING GIJON",
    "SPORTING": "SPORTING GIJON",
    "REAL VALLADOLID CF": "VALLADOLID",
    "CD LEGANES": "LEGANES",
    "CD MIRANDES": "MIRANDES",
    "SD HUESCA": "HUESCA",
    "CULTURAL Y DEPORTIVA LEONESA": "CULTURAL LEONESA",
    "C LEONESA": "CULTURAL LEONESA",
    "ALEMANIA": "GERMANY",
    "JAPON": "JAPAN",
    "ISLANDIA": "ICELAND",
    "FINLANDIA": "FINLAND",
    "INGLATERRA": "INGLATERRA",
    "ENGLAND": "INGLATERRA",
    "ESCOCIA": "ESCOCIA",
    "SCOTLAND": "ESCOCIA",
    "GALES": "GALES",
    "WALES": "GALES",
    "RUMANIA": "RUMANIA",
    "ROMANIA": "RUMANIA",
    "NUEVA ZELANDA": "NUEVA ZELANDA",
    "NEW ZEALAND": "NUEVA ZELANDA",
    "SUIZA": "SUIZA",
    "SWITZERLAND": "SUIZA",
    "TUNEZ": "TUNEZ",
    "TUNISIA": "TUNEZ",
    "MARRUECOS": "MARRUECOS",
    "MOROCCO": "MARRUECOS",
    "BELGIUM": "BELGICA",
    "BRAZIL": "BRASIL",
    "UNITED STATES": "EE UU",
    "USA": "EE UU",
    "ESTADOS UNIDOS": "EE UU",
    "COTE D IVOIRE": "COSTA DE MARFIL",
    "IVORY COAST": "COSTA DE MARFIL",
    "CURACAO": "CURACAO",
    "TURKEY": "TURQUIA",
    "TURKIYE": "TURQUIA",
    "IRAN": "IRAN",
    "FRANCE": "FRANCIA",
    "EGYPT": "EGIPTO",
    "SAUDI ARABIA": "ARABIA SAUDI",
    "CAPE VERDE": "CABO VERDE",
    "NETHERLANDS": "HOLANDA",
    "PAISES BAJOS": "HOLANDA"
};

const TEAM_LOGO_FILES = {
    "ATLETICOMADRID": "/static/img/team_logos/ATLETICO_MADRID.png",
    "OSASUNA": "/static/img/team_logos/OSASUNA.png",
    "CULTURALLEONESA": "/static/img/team_logos/CULTURAL_LEONESA.png",
    "SPORTINGGIJON": "/static/img/team_logos/SPORTING_GIJON.png",
    "ALBACETE": "/static/img/team_logos/ALBACETE.png",
    "LACORUNA": "/static/img/team_logos/DEPORTIVO_LA_CORUNA.png",
    "RACINGSANTANDER": "/static/img/team_logos/RACING_SANTANDER.png"
};

function logoLookupKey(name) {
    const key = normalizeName(name);
    return getLogoAliasIndex().get(key) || key;
}

function getLogoAliasIndex() {
    if (logoAliasIndex) return logoAliasIndex;
    logoAliasIndex = new Map();
    for (const [rawName, canonicalName] of Object.entries(TEAM_LOGO_ALIASES)) {
        logoAliasIndex.set(normalizeName(rawName), normalizeName(canonicalName));
    }
    return logoAliasIndex;
}

function logoBadge(name, logo) {
    if (logo) {
        return `<span class="team-badge has-logo"><img src="${escapeHtml(logo)}" alt=""></span>`;
    }
    return `<span class="team-badge">${escapeHtml(teamToken(name))}</span>`;
}

function teamCell(name, side = "left", logo = "") {
    return `<div class="team-cell ${side}">
        ${logoBadge(name, logo)}
        <span class="match-team">${escapeHtml(getShortName(name))}</span>
    </div>`;
}

function fixtureInline(homeName, awayName, homeLogo = "", awayLogo = "") {
    return `<div class="fixture-inline">
        <span class="fixture-name fixture-name-home">${escapeHtml(getShortName(homeName))}</span>
        <span class="fixture-crest-pair">
            ${logoBadge(homeName, homeLogo)}
            <span class="fixture-sep">-</span>
            ${logoBadge(awayName, awayLogo)}
        </span>
        <span class="fixture-name fixture-name-away">${escapeHtml(getShortName(awayName))}</span>
    </div>`;
}

function findStandingContext(teamName) {
    const cacheKey = normalizeName(teamName);
    if (standingContextCache.has(cacheKey)) return standingContextCache.get(cacheKey);
    const standings = state.data.standings || {};
    const needle = cacheKey;
    for (const cat of ["primera", "segunda"]) {
        for (const team of (standings[cat] || [])) {
            if (normalizeName(team.n) === needle) {
                const result = {
                    pos: team.pos ?? "-",
                    pts: team.pts ?? "-",
                    pj: team.pj ?? "-"
                };
                standingContextCache.set(cacheKey, result);
                return result;
            }
        }
    }
    standingContextCache.set(cacheKey, null);
    return null;
}

function findTeamLogo(name) {
    return fixedTeamLogo(name);
}
