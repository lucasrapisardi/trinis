// PATH: src/types/next-auth.d.ts
import "next-auth";
import "next-auth/jwt";

declare module "next-auth" {
  interface User {
    id: string;
    email: string;
    full_name: string | null;
    tenant_id: string;
    is_owner: boolean;
    tour_completed: boolean;
    access_token: string;
    refresh_token: string;
  }

  interface Session {
    user: {
      id: string;
      email: string;
      full_name: string | null;
      tenant_id: string;
      is_owner: boolean;
    tour_completed: boolean;
      access_token: string;
      refresh_token: string;
    };
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    id: string;
    full_name: string | null;
    tenant_id: string;
    is_owner: boolean;
    tour_completed: boolean;
    access_token: string;
    refresh_token: string;
  }
}
