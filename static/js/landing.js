/* Landing pública: año dinámico + datos estructurados (JSON-LD).
   Va en un archivo externo porque la CSP del sitio es `script-src 'self'`
   (sin 'unsafe-inline'): un <script> inline nunca llegaría a ejecutarse. */
(function () {
  'use strict';

  var year = document.getElementById('year');
  if (year) year.textContent = String(new Date().getFullYear());

  var structuredData = {
    '@context': 'https://schema.org',
    '@type': 'WebApplication',
    name: 'Liga de Maestros',
    applicationCategory: 'GameApplication,SportsApplication',
    operatingSystem: 'Web',
    inLanguage: 'es',
    offers: { '@type': 'Offer', price: '0', priceCurrency: 'EUR' },
    featureList: [
      'Quiniela 1X2 competitiva humanos vs IA',
      'Resultados y marcadores en directo',
      'Ranking histórico y porra del pleno',
      'Quiz semanal de fútbol y arcade retro'
    ]
  };

  var sd = document.createElement('script');
  sd.type = 'application/ld+json';
  sd.textContent = JSON.stringify(structuredData);
  document.head.appendChild(sd);
})();
