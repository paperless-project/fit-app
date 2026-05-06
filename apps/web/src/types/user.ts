export type Gender = 'hombre' | 'mujer' | 'no_binario' | 'prefiero_no_decirlo' | 'otro';

export interface UserRead {
  id: string;
  email: string;
  is_active: boolean;
  is_superuser: boolean;
  is_verified: boolean;
  first_name: string | null;
  last_name: string | null;
  birth_date: string | null;
  gender: Gender | null;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}
