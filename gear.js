/* Извлечение оборудования музыканта из текста статьи Википедии.
   Распознаёт бренды и модели гитар, басов, усилителей, кабинетов, педалей/эффектов,
   ударных, тарелок, клавишных, звукоснимателей и аксессуаров. */
(function (root) {
  const CATS = {
    guitars:  { ru: 'Гитары', icon: '🎸' },
    bass:     { ru: 'Бас-гитары', icon: '🎸' },
    amps:     { ru: 'Усилители', icon: '🔊' },
    cabs:     { ru: 'Кабинеты и динамики', icon: '📦' },
    fx:       { ru: 'Педали и эффекты', icon: '🎛️' },
    drums:    { ru: 'Ударная установка', icon: '🥁' },
    cymbals:  { ru: 'Тарелки', icon: '🥁' },
    keys:     { ru: 'Клавишные и синтезаторы', icon: '🎹' },
    pickups:  { ru: 'Звукосниматели и железо', icon: '🧲' },
    acc:      { ru: 'Струны, медиаторы, палочки', icon: '🪕' },
  };
  // [шаблон бренда, категория по умолчанию, строгий (бренд = распространённое слово/фамилия)]
  const BRANDS = [
    // гитары
    ['Gibson', 'guitars', 1], ['Fender', 'guitars', 0], ['Epiphone', 'guitars', 0], ['Gretsch', 'guitars', 0],
    ['Rickenbacker', 'guitars', 0], ['Ibanez', 'guitars', 0], ['ESP', 'guitars', 1], ['LTD', 'guitars', 1],
    ['Jackson', 'guitars', 1], ['Charvel', 'guitars', 0], ['Kramer', 'guitars', 1], ['Schecter', 'guitars', 0],
    ['PRS', 'guitars', 0], ['Paul Reed Smith', 'guitars', 0], ['B\\.?\\s?C\\.? Rich', 'guitars', 0], ['Dean', 'guitars', 1],
    ['Music Man', 'guitars', 0], ['Ernie Ball Music Man', 'guitars', 0], ['Steinberger', 'guitars', 0], ['Danelectro', 'guitars', 0],
    ['Mosrite', 'guitars', 0], ['Guild', 'guitars', 1], ['Martin', 'guitars', 1], ['C\\. ?F\\. ?Martin', 'guitars', 0],
    ['Taylor', 'guitars', 1], ['Ovation', 'guitars', 1], ['Takamine', 'guitars', 0], ['Washburn', 'guitars', 1],
    ['Hamer', 'guitars', 1], ['EVH', 'guitars', 0], ['Strandberg', 'guitars', 0], ['Mayones', 'guitars', 0],
    ['Kiesel', 'guitars', 0], ['Carvin', 'guitars', 1], ['Yamaha', 'guitars', 1], ['Höfner', 'bass', 0], ['Hofner', 'bass', 0],
    ['Gibson Les Paul', 'guitars', 0], ['Les Paul', 'guitars', 1], ['Stratocaster', 'guitars', 0], ['Telecaster', 'guitars', 0],
    ['Jazzmaster', 'guitars', 0], ['Parker', 'guitars', 1], ['Godin', 'guitars', 1], ['Duesenberg', 'guitars', 0],
    ['Silvertone', 'guitars', 0], ['Harmony', 'guitars', 1], ['Kay', 'guitars', 1], ['National', 'guitars', 1],
    ['Dobro', 'guitars', 0], ['Line 6 Variax', 'guitars', 0], ['Squier', 'guitars', 0], ['Tokai', 'guitars', 0],
    ['Aria', 'guitars', 1], ['Framus', 'guitars', 0], ['Vigier', 'guitars', 0], ['Suhr', 'guitars', 0],
    ['Tom Anderson', 'guitars', 0], ['Zemaitis', 'guitars', 0], ['Gordon Smith', 'guitars', 0], ['Solar Guitars', 'guitars', 0],
    // басы
    ['Warwick', 'bass', 1], ['Spector', 'bass', 1], ['Sadowsky', 'bass', 0], ['Lakland', 'bass', 0], ['Fodera', 'bass', 0],
    ['Alembic', 'bass', 0], ['Status Graphite', 'bass', 0], ['Wal', 'bass', 1], ['Ken Smith', 'bass', 0], ['Modulus', 'bass', 0],
    // усилители
    ['Marshall', 'amps', 1], ['Mesa[/ -]?Boogie', 'amps', 0], ['Mesa', 'amps', 1], ['Vox', 'amps', 1], ['Orange', 'amps', 1],
    ['Hiwatt', 'amps', 0], ['Peavey', 'amps', 0], ['ENGL', 'amps', 0], ['Engl', 'amps', 1], ['Diezel', 'amps', 0],
    ['Bogner', 'amps', 0], ['Soldano', 'amps', 0], ['Laney', 'amps', 1], ['Randall', 'amps', 1], ['Ampeg', 'amps', 0],
    ['Sunn', 'amps', 1], ['Kustom', 'amps', 1], ['Hughes (?:&|and) Kettner', 'amps', 0], ['Friedman', 'amps', 1],
    ['Dumble', 'amps', 0], ['Matchless', 'amps', 1], ['Two-Rock', 'amps', 0], ['Gallien-Krueger', 'amps', 0],
    ['Trace Elliot', 'amps', 0], ['Hartke', 'amps', 0], ['SWR', 'amps', 0], ['Aguilar', 'amps', 1], ['Eden', 'amps', 1],
    ['Markbass', 'amps', 0], ['Blackstar', 'amps', 1], ['Magnatone', 'amps', 0], ['Supro', 'amps', 0], ['Selmer', 'amps', 1],
    ['WEM', 'amps', 1], ['Watkins', 'amps', 1], ['Sound City', 'amps', 1], ['Revv', 'amps', 0], ['Victory Amps', 'amps', 0],
    ['Dr\\.? Z', 'amps', 0], ['Fractal Audio', 'amps', 0], ['Axe-Fx', 'amps', 0], ['Kemper', 'amps', 0], ['Neural DSP', 'amps', 0],
    ['Darkglass', 'fx', 0], ['Tech 21', 'fx', 0], ['SansAmp', 'fx', 0], ['Rivera', 'amps', 1], ['Budda', 'amps', 0],
    ['Splawn', 'amps', 0], ['Krank', 'amps', 0], ['Egnater', 'amps', 0], ['Carr', 'amps', 1],
    ['Acoustic Control', 'amps', 0], ['Park', 'amps', 1], ['Bad Cat', 'amps', 0], ['Divided by 13', 'amps', 0],
    // кабинеты / динамики
    ['Celestion', 'cabs', 0], ['Electro-Voice', 'cabs', 0], ['Jensen', 'cabs', 1], ['Eminence', 'cabs', 1],
    // эффекты
    ['Boss', 'fx', 1], ['MXR', 'fx', 0], ['Electro-Harmonix', 'fx', 0], ['EHX', 'fx', 0], ['DigiTech', 'fx', 0], ['Digitech', 'fx', 0],
    ['TC Electronic', 'fx', 0], ['T\\.C\\. Electronic', 'fx', 0], ['Eventide', 'fx', 0], ['Strymon', 'fx', 0], ['Fulltone', 'fx', 0],
    ['Klon', 'fx', 0], ['Maestro', 'fx', 1], ['Echoplex', 'fx', 0], ['Binson', 'fx', 0], ['Leslie', 'fx', 1],
    ['Uni-Vibe', 'fx', 0], ['Univibe', 'fx', 0], ['Univox', 'fx', 0], ['Arbiter', 'fx', 0], ['Dallas Arbiter', 'fx', 0],
    ['Sola Sound', 'fx', 0], ['Colorsound', 'fx', 0], ['Morley', 'fx', 1], ['Dunlop', 'fx', 0], ['Jim Dunlop', 'fx', 0],
    ['Pro Co', 'fx', 0], ['ProCo', 'fx', 0], ['Zoom', 'fx', 1], ['Line 6', 'fx', 0], ['Rocktron', 'fx', 0], ['Lexicon', 'fx', 0],
    ['Keeley', 'fx', 0], ['JHS', 'fx', 0], ['Walrus Audio', 'fx', 0], ['EarthQuaker', 'fx', 0], ['Way Huge', 'fx', 0],
    ['Z\\.? ?Vex', 'fx', 0], ['Death By Audio', 'fx', 0], ['Analog Man', 'fx', 0], ['Analogman', 'fx', 0], ['Xotic', 'fx', 0],
    ['Wampler', 'fx', 0], ['Mooer', 'fx', 0], ['Source Audio', 'fx', 0], ['Bradshaw', 'fx', 1], ['Heil', 'fx', 1],
    ['Ibanez Tube Screamer', 'fx', 0], ['Tube Screamer', 'fx', 0], ['Big Muff', 'fx', 0], ['Cry ?Baby', 'fx', 0], ['Fuzz Face', 'fx', 0],
    ['Tone Bender', 'fx', 0], ['Whammy', 'fx', 1], ['EBow', 'fx', 0], ['E-Bow', 'fx', 0], ['Talk ?box', 'fx', 0],
    ['Roland', 'keys', 1], ['Korg', 'keys', 0], ['Fishman', 'pickups', 0], ['Mu-Tron', 'fx', 0], ['Mutron', 'fx', 0],
    ['Electro Harmonix', 'fx', 0], ['Foxx', 'fx', 1], ['Thomas Organ', 'fx', 0], ['Fuzz-Tone', 'fx', 0], ['Pigtronix', 'fx', 0],
    ['Chase Bliss', 'fx', 0], ['Catalinbread', 'fx', 0], ['Suhr Riot', 'fx', 0], ['Eventide H9', 'fx', 0], ['Axess', 'fx', 1],
    ['Voodoo Lab', 'fx', 0], ['RJM', 'fx', 0], ['Custom Audio Electronics', 'fx', 0], ['Dunlop Cry Baby', 'fx', 0],
    // ударные
    ['Tama', 'drums', 0], ['Pearl', 'drums', 1], ['Ludwig', 'drums', 1], ['DW', 'drums', 1], ['Drum Workshop', 'drums', 0],
    ['Sonor', 'drums', 0], ['Mapex', 'drums', 0], ['Premier', 'drums', 1], ['Slingerland', 'drums', 0], ['Rogers', 'drums', 1],
    ['Pork Pie', 'drums', 0], ['ddrum', 'drums', 0], ['Simmons', 'drums', 1], ['Gretsch drums', 'drums', 0], ['Yamaha drums', 'drums', 0],
    ['Remo', 'acc', 1], ['Evans', 'acc', 1], ['Aquarian', 'acc', 1], ['Vic Firth', 'acc', 0], ['Pro-?Mark', 'acc', 0], ['Vater', 'acc', 1],
    ['Ahead', 'acc', 1], ['Axis', 'drums', 1], ['Trick', 'drums', 1], ['Roland V-Drums', 'drums', 0], ['Craviotto', 'drums', 0],
    // тарелки
    ['Zildjian', 'cymbals', 0], ['Sabian', 'cymbals', 0], ['Paiste', 'cymbals', 0], ['Meinl', 'cymbals', 0], ['Istanbul Agop', 'cymbals', 0],
    ['Istanbul Mehmet', 'cymbals', 0], ['UFIP', 'cymbals', 0], ['Dream Cymbals', 'cymbals', 0], ['Wuhan', 'cymbals', 1],
    // клавишные
    ['Hammond', 'keys', 1], ['Moog', 'keys', 0], ['Minimoog', 'keys', 0], ['Mellotron', 'keys', 0], ['Fender Rhodes', 'keys', 0],
    ['Rhodes', 'keys', 1], ['Wurlitzer', 'keys', 0], ['Clavinet', 'keys', 0], ['Hohner', 'keys', 0], ['Farfisa', 'keys', 0],
    ['Nord', 'keys', 1], ['Kurzweil', 'keys', 0], ['Oberheim', 'keys', 0], ['Sequential Circuits', 'keys', 0], ['Prophet-5', 'keys', 0],
    ['ARP', 'keys', 1], ['Steinway', 'keys', 0], ['Kawai', 'keys', 0], ['Vox Continental', 'keys', 0], ['E-mu', 'keys', 0],
    ['Ensoniq', 'keys', 0], ['Fairlight', 'keys', 0], ['Synclavier', 'keys', 0], ['Access Virus', 'keys', 0], ['Chamberlin', 'keys', 0],
    // звукосниматели и железо
    ['Seymour Duncan', 'pickups', 0], ['EMG', 'pickups', 0], ['DiMarzio', 'pickups', 0], ['Bare Knuckle', 'pickups', 0],
    ['Lace', 'pickups', 1], ['Bill Lawrence', 'pickups', 0], ['Floyd Rose', 'pickups', 0], ['Kahler', 'pickups', 0],
    ['Bigsby', 'pickups', 0], ['Schaller', 'pickups', 0], ['Sperzel', 'pickups', 0], ['Gotoh', 'pickups', 0], ['Grover', 'pickups', 1],
    ['TonePros', 'pickups', 0], ['Hipshot', 'pickups', 0], ['Evertune', 'pickups', 0], ['Fralin', 'pickups', 0],
    // струны / медиаторы
    ["D'Addario", 'acc', 0], ['Ernie Ball', 'acc', 0], ['Dean Markley', 'acc', 0], ['GHS', 'acc', 0], ['Elixir', 'acc', 1],
    ['Rotosound', 'acc', 0], ['DR Strings', 'acc', 0], ['Dunlop Tortex', 'acc', 0], ['Tortex', 'acc', 0], ['Planet Waves', 'acc', 0],
    ['Dunlop Jazz III', 'acc', 0], ['V-Picks', 'acc', 0], ['Kerly', 'acc', 0], ['La Bella', 'acc', 0], ['Thomastik', 'acc', 0],
  ];
  const NOUN = {
    guitars: /^(guitars?|electric|acoustic|semi-acoustic|archtop|twelve-string|12-string|hollow-?body|solid-?body|signature)$/i,
    bass: /^(bass(es)?|bass guitars?)$/i,
    amps: /^(amps?|amplifiers?|amplification|heads?|combos?|stacks?|preamps?|rigs?|modell?ers?|profilers?)$/i,
    cabs: /^(cabs?|cabinets?|speakers?)$/i,
    fx: /^(pedals?|effects?|wah|fuzz|distortion|overdrive|delay|reverb|chorus|flanger|phaser|echo|octave|processors?|boards?|pedalboards?|multi-effects?|units?)$/i,
    drums: /^(drums?|kits?|snares?|toms?|hardware|kick)$/i,
    cymbals: /^(cymbals?|crash|ride|hi-?hats?|splash|china)$/i,
    keys: /^(organs?|pianos?|synths?|synthesizers?|keyboards?)$/i,
    pickups: /^(pickups?|humbuckers?|tremolos?|bridges?|tuners?)$/i,
    acc: /^(strings?|picks?|plectrums?|sticks|drumsticks|drumheads|heads|straps?)$/i,
  };
  const KW = [
    ['drums', /\b(V-?Drums|TD-?\d+|SPD-?\w+|electronic drums?)/i],
    ['fx', /\b(tuners?|DT-\d+|Pitchblack|Polytune|TU-\d)\b/i],
    ['cabs', /\b(cabs?|cabinets?|4\s?[x×]\s?12|2\s?[x×]\s?12|1\s?[x×]\s?12|8\s?[x×]\s?10|4\s?[x×]\s?10|1960[AB]?\b|Celestion|Vintage 30|Greenback)/i],
    ['fx', /\b(pedals?|wah|fuzz|Tube Screamer|TS-?\d{1,3}|DS-[12]|SD-1|CE-[125]|DD-\d|HM-2|OD-[1-3]|MT-2|BD-2|RV-\d|PH-\d|Big Muff|Rat\b|Whammy|Cry ?Baby|Fuzz Face|Tone Bender|Uni-?Vibe|Echoplex|Space Echo|RE-201|Echorec|delay|chorus|flanger|phaser|Phase \d+|overdrive|octave|Octavia|talk ?box|E-?Bow|noise gate|looper|harmoni[sz]er|Memory Man|Small Stone|Electric Mistress|Dyna Comp|Carbon Copy|POG|POD|Helix|HX Stomp|G-Major|G-System|H3000|H9|Centaur|OCD|Leslie|compressor|volume pedal|multi-?effects?|effects? (unit|processor)|Fuzz-Tone|Super-Fuzz|Q-Tron|DL4|M9|M13|Micro Amp|Flashback|Hall of Fame|Mu-Tron|SansAmp|Microtubes|B7K|Rotovibe|vibe\b)/i],
    ['amps', /\b(amps?\b|amplifiers?|heads?\b|combo|JCM\s?\d+|JVM|DSL|Plexi|Super Lead|Super Bass|JTM\s?\d*|Silver Jubilee|Major\b|Twin Reverb|Twin\b|Deluxe Reverb|Bassman|Princeton|Super Reverb|Champ\b|Vibroverb|Vibrolux|Showman|Hot Rod|Blues Deluxe|Blues Junior|Bandmaster|AC\s?-?(15|30|50|100)|Rectifier|Mark (I{1,3}|IV|V|IIC\+?)|Lone Star|Road King|5150|6505|SLO|VH4|Herbert|Uberschall|Ecstasy|Shiva|Rockerverb|Thunderverb|Tiny Terror|OR\s?\d+|SVT|B-15|Portaflex|JC-?120|Jazz Chorus|Axe-?Fx|Profiler|Quad Cortex|Dual Caliber|Invective|Savage|Powerball|Fireball|Ironball|Triple Crown|Big Bottom|Custom 100|DR103|Plexi|Bluesbreaker amp|Stealth|Thunderbird amp)/i],
    ['keys', /\b(organs?|synth|synthesi[sz]ers?|pianos?|keyboards?|Minimoog|Moog\b|B-?3|C-?3|Mellotron|Rhodes|Wurlitzer|Clavinet|DX-?7|Jupiter|Juno|Prophet|Oberheim|Taurus|Hammond|Nord|Triton|Motif|M1\b|Continental)/i],
    ['cymbals', /\b(cymbals?|crash|ride|hi-?hats?|china|splash|K Custom|A Custom|AAX|HHX|HH\b|2002|Rude|Signature Series)/i],
    ['drums', /\b(drums?|drum ?kit|kit\b|snare|toms?|kick|double bass pedal|Starclassic|Iron Cobra|Speed Cobra|Masters|Reference|Collector'?s|Black Beauty|Supraphonic|Vistalite|Superstar|Granstar|Session|Export|Masterworks|Saturn|Absolute|SQ2)/i],
    ['bass', /\b(bass(es)?\b|Precision|P-Bass|Jazz Bass|J-Bass|Thunderbird|StingRay|Stingray|4001|4003|Violin|500\/1|Streamer|Thumb|Corvette|Bongo|Dingwall)/i],
    ['pickups', /\b(pickups?|humbuckers?|single-?coils?|PAF|EMG \d+|Invader|JB\b|SH-\d+|Super Distortion|Tone Zone|Evolution|X2N|Floyd Rose|tremolo (system|bridge|unit)|Kahler|Bigsby|locking tuners?|bridge)/i],
    ['acc', /\b(strings|picks?|plectrums?|sticks|drumsticks|drumheads|heads\b|Tortex|Jazz III|straps?|capo|slide|Slinky|Regular Slinky|Power Slinky)/i],
    ['guitars', /\b(guitars?|Les Paul|SG\b|Explorer|Flying V|Firebird|ES-\d+|L-5|Super 400|Stratocaster|Strat\b|Telecaster|Tele\b|Jazzmaster|Jaguar|Mustang|Falcon|White Falcon|Country Gentleman|Duo Jet|Randy Rhoads|Rhoads|Soloist|King V|Kelly|Dinky|Warrior|Warlock|Bich|Mockingbird|Ironbird|ML\b|Razorback|JEM|RG\d*|Iceman|Destroyer|Axis|Silhouette|Albert Lee|Majesty|JP\d+|Wolfgang|Frankenstrat|Casino|Sheraton|Riviera|D-\d+|Custom 24|Custom 22|Singlecut|SE\b|KH-\d+|M-II|Eclipse|Horizon|Viper|Hellraiser|Blackjack|C-1|Avenger|Synyster|Ultra|Deluxe|Standard|Custom Shop|Signature)/i],
  ];
  const STOP = new Set(['The','In','On','At','And','He','She','His','Her','It','Its','As','For','With','During','After','Before','When','While','Records','Hall','Award','Awards','Prize','Street','University','School','College','Studios','Studio','Company','Corporation','Inc','Ltd','Foundation','Center','Centre','Theatre','Theater','Arena','Festival','Park','House','Museum','Band','Group','They','Their','This','That','These','Those','Also','But','Or','From','To','By','Of','A','An','Was','Were','Is','Are','Had','Has','Have','I','We','You','My','Our','Jr','Sr','County','City','Island','Beach','Avenue','Road','Square','Productions','Entertainment','Music','Musical','Instruments','Electronics','Recording','Registry','Academy','Trust','Manufacturing','Magazine','World','Player','Award','Prize','Records','Label','USA','UK','Japan','Germany','Mexico','Korea','Indonesia','China']);
  const MODEL_TOK = /^(?:[A-Z0-9][A-Za-z0-9\-\/+'’.]*|[a-z]{0,3}\d[\w\-\/+.]*|[IVX]{1,4}\+?|&|Jr\.?)$/;
  const LOWER_MODEL = /^(wah|fuzz|plus|special|custom|junior|deluxe|standard|studio|classic|reissue|wah-wah|vibe|echo|bass)$/i;
  const GEAR_CTX = /\b(guitar|bass|amp|amplifier|pedal|effect|drum|cymbal|kit|keyboard|organ|synth|piano|strings|pickup|endors|signature|plays?|played|playing|uses?|used|using|rig|gear|equipment|tone|sound|model|custom|stage|tour|record)/i;

  const NEG = /^(Premier Guitar|Guitar World|Guitar Player|Total Guitar|Les Paul Award|Les Paul Foundation|National Recording|National Academy|National Film|Martin Luther|Marshall Mathers|Marshall Tucker|Taylor Swift|Taylor Hawkins|Dean Martin|Jackson Browne|Jackson 5|Michael Jackson|Janet Jackson|Orange County|Orange Juice|Pearl Jam|Pearl Harbor|Hammond B-3 Organ Trio|Ludwig van|Rhodes Scholar|Boss Hog|Zoom call|Mesa, Arizona|Evans Blue|Nord Stage 2? festival)/i;
  const esc = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const BRAND_RE = new RegExp('(?<![\\w\'’-])(' + BRANDS.map(b => b[0]).sort((a, b) => b.length - a.length).join('|') + ')(?![\\w\'’-])', 'g');
  const brandInfo = name => {
    let best = null;
    for (const b of BRANDS) { const re = new RegExp('^(?:' + b[0] + ')$', 'i'); if (re.test(name) && (!best || b[0].length > best[0].length)) best = b; }
    return best;
  };

  function sentences(text) {
    return text.replace(/\n+/g, ' \n ').split(/(?<=[.!?])\s+(?=[A-Z"“(])|\s\n\s/).map(s => s.trim()).filter(s => s.length > 3);
  }

  function categorize(item, brandCat, after, sentence) {
    // 1) модельные ключевые слова в самом названии
    for (const [cat, re] of KW) if (re.test(item.replace(/^\S+\s?/, ''))) {
      // ключевые слова тарелок/ударных применяем только к брендам ударных
      if ((cat === 'cymbals' || cat === 'drums') && !['drums', 'cymbals', 'acc'].includes(brandCat) && !(cat === 'drums' && /V-?Drums|TD-?\d|SPD|electronic drum/i.test(item))) continue;
      if (cat === 'bass' && (brandCat === 'amps' || brandCat === 'fx')) continue;
      if (cat === 'guitars' && ['amps', 'fx', 'drums', 'cymbals', 'keys', 'acc', 'cabs'].includes(brandCat) && !/guitars?/i.test(item)) continue;
      return cat;
    }
    // 2) существительное после бренда («Marshall amps», «Pearl drums»)
    for (const [cat, re] of Object.entries(NOUN)) if (after && re.test(after)) return cat;
    return brandCat;
  }

  function extract(text, opts = {}) {
    const found = new Map();
    for (const s of sentences(text || '')) {
      BRAND_RE.lastIndex = 0;
      let m;
      while ((m = BRAND_RE.exec(s))) {
        const brand = m[1];
        if (NEG.test(s.slice(m.index, m.index + 40))) continue;
        const info = brandInfo(brand); if (!info) continue;
        const [, bcat, strict] = info;
        // модель: следующие токены
        const rest = s.slice(m.index + brand.length).split(/\s+/).filter(Boolean);
        const model = []; let after = '';
        for (let i = 0; i < rest.length && model.length < 4; i++) {
          let t = rest[i];
          const endPunct = /[,;:)\]"”]$|\.$/.test(t) && !/^[A-Z]{1,3}\.$|^\d+\.\d+$/.test(t);
          t = t.replace(/^[("“]+/, '').replace(/[,;:)\]"”.]+$/, '');
          if (!t) break;
          if (STOP.has(t)) break;
          if (MODEL_TOK.test(t) || (model.length && LOWER_MODEL.test(t)) || (!model.length && LOWER_MODEL.test(t) && /wah|fuzz|vibe|echo/i.test(t))) { model.push(t); if (endPunct) break; continue; }
          after = t.toLowerCase(); break;
        }
        // строгие бренды (фамилии/общие слова) — нужна модель, «гир-существительное» или явный гир-контекст
        const nounHit = after && Object.values(NOUN).some(re => re.test(after));
        if (strict && !model.length && !nounHit) continue;
        if (strict && model.length && !nounHit && !GEAR_CTX.test(s)) continue;
        // отсекаем «Gibson Guitar Corporation» и т.п.
        let name = (brand + ' ' + model.join(' ')).trim().replace(/\s+/g, ' ');
        name = name.replace(/\s(Guitar|Guitars|Corporation|Company|Inc|Amplification|Amplifiers|Manufacturing|Drums|Cymbals|Strings|Electronics|Musical|Instruments|USA)$/i, '');
        if (/^(Martin|Taylor|Dean|Jackson|Gibson|Kramer|Rogers|Randall|Leslie|Evans|Remo|Marshall|Hammond|Rhodes|Ludwig|Pearl|Orange|Premier|Simmons|Parker|Burns|Carr|Friedman|Lace|Harmony|National|Grover|Jensen|Wal|Nord|Ahead|Trick|Axis|Kay|Aria|Godin|Guild|Washburn|Hamer|Vater|Selmer|Watkins|Eden|Aguilar|Matchless|Zoom|Boss|Maestro|Morley|Heil|Elixir|Foxx|Laney|Sunn|Kustom|Rivera|Wuhan|Yamaha|Roland|ESP|LTD|Ovation|Mesa|Engl|Bradshaw|Whammy|Les Paul|Carvin|Axess|Park|Sound City|WEM)\s[A-Z][a-z]+$/.test(name) && !/\d/.test(name) && !nounHit) {
          // «Martin Luther», «Taylor Hawkins», «Gibson Brothers» — не гитары
          const second = name.split(' ').slice(1).join(' ');
          if (!/^(Les|Paul|Flying|Explorer|Firebird|Custom|Standard|Special|Deluxe|Junior|Studio|Classic|Super|Plexi|Major|Rectifier|Mark|Dual|Triple|Starclassic|Masters|Reference|Session|Export|Black|Silver|Rockerverb|Tiny|Thunderverb|Jazz|Precision|Continental|Twin|Bassman|Stage|Lead|Signature|Soloist|Warrior|Kelly|King|Rhoads|Randy|Dinky|Wolfgang|Iceman|Destroyer|Horizon|Eclipse|Viper|Phoenix|Mustang|Jaguar|Telecaster|Stratocaster|Jazzmaster|Supraphonic|Vistalite|Superstar|Granstar|Taurus|Prophet|Juno|Jupiter|Triton|Motif|Electro|Combo|Bluesbreaker|Guv|Valvestate|Silver|Plexi|Sunburst|Goldtop|Classic|Tube|Metal|Heavy|Hellraiser)/.test(second)) continue;
        }
        if (name.length < 3) continue;
        name = name.replace(/\b(Jazzmaster|Stratocaster|Telecaster|SG|Flying V|Les Paul|Explorer|Firebird|Strat|Jaguar|Mustang|Rickenbacker)s\b/, '$1');
        const cat = categorize(name, bcat, after, s);
        const display = /^(Les Paul|Stratocaster|Telecaster|Jazzmaster)$/i.test(name) ? name : name;
        const key = cat + '|' + display.toLowerCase();
        const e = found.get(key) || { cat, name: display, n: 0, ctx: s.length > 320 ? s.slice(0, 317) + '…' : s, specific: model.length > 0 };
        e.n++; found.set(key, e);
      }
    }
    // убрать «голые» бренды, если есть конкретная модель того же бренда в той же категории
    const items = [...found.values()];
    const out = items.filter(e => !(!e.specific && items.some(o => o !== e && o.cat === e.cat && o.specific && o.name.toLowerCase().startsWith(e.name.toLowerCase() + ' '))));
    // «Stratocaster» без бренда → в «Fender Stratocaster»
    const out2 = out.filter(e => {
      const full = out.find(o => o !== e && o.cat === e.cat && o.name.toLowerCase().endsWith(' ' + e.name.toLowerCase()) && o.name.split(' ').length === e.name.split(' ').length + 1);
      if (full) { full.n += e.n; return false } return true;
    });
    const by = {};
    for (const e of out2) (by[e.cat] ||= []).push(e);
    for (const k in by) by[k].sort((a, b) => b.n - a.n || a.name.localeCompare(b.name));
    return by;
  }

  function merge(...lists) {
    const by = {};
    for (const l of lists) for (const [cat, arr] of Object.entries(l || {})) for (const e of arr) {
      const x = (by[cat] ||= []); const o = x.find(z => z.name.toLowerCase() === e.name.toLowerCase());
      if (o) { o.n += e.n; if (e.who && o.who && !o.who.includes(e.who)) o.who += ', ' + e.who; } else x.push({ ...e });
    }
    for (const k in by) by[k].sort((a, b) => b.n - a.n);
    return by;
  }

  root.GEAR = { extract, merge, CATS, ORDER: ['guitars', 'bass', 'amps', 'cabs', 'fx', 'pickups', 'drums', 'cymbals', 'keys', 'acc'] };
})(typeof window !== 'undefined' ? window : globalThis);
