export interface Artist {
    name: string;
    anv: string;
    join: string;
    role: string;
    tracks: string;
    id: number;
    resource_url: string;
  }
  
  export interface Track {
    position: string;
    type_: string;
    artist: string;
    artists: Artist[];
    title: string;
    duration: string;
    cd_position: number;
    full_name: string;
    deck_number: number;
  }

  export interface Playlist {
    name: string;
    tracks: Track[];
  }