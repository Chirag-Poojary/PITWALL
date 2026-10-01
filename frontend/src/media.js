// Media used on the fan pages. Swap these for your own at any time.
//
// Hero video: if you drop a file at frontend/public/media/hero.mp4 it is used first
// (no YouTube branding). Otherwise the YouTube clip below plays muted in the background.
// Images: Wikimedia Commons files (Creative Commons). Drop your own JPGs into
// frontend/public/media/ and change the paths here, e.g. '/media/grid.jpg'.

const commons = (file, width = 1600) =>
  `https://commons.wikimedia.org/wiki/Special:FilePath/${encodeURIComponent(file)}?width=${width}`

export const MEDIA = {
  heroLocalVideo: '/media/hero.mp4',
  heroYouTubeId: 'smp_EABcsTw', // onboard pole lap
  carVideoId: 'kV2fo40nIHs', // "How A Formula 1 Car is Made"
  carVideoAltId: 'CktpA3To7T4', // "How It's Made: Formula 1 Cars"
  images: {
    auth: commons('Formula_1_Ferrari.jpg'),
    car: commons('Renault_Formula_One_racing_car_(49667991997).jpg'),
    history: commons('2001_Williams_FW23_Formula_1_Car_(53436323520).jpg'),
    weekend: commons('BMW_Formula_1_race_car.jpg'),
  },
}

export const ytEmbed = (id, opts = '') => `https://www.youtube-nocookie.com/embed/${id}?rel=0&modestbranding=1${opts}`
export const ytWatch = (id) => `https://www.youtube.com/watch?v=${id}`
